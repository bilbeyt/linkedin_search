from enum import Enum
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import structlog
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException, WebDriverException, JavascriptException
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from time import sleep
from urllib3.exceptions import ReadTimeoutError


structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.WriteLoggerFactory(
        file=Path("app").with_suffix(".log").open("wt")
    )
)

logger = structlog.getLogger(__name__)


class Location(Enum):
    BERLIN = "103035651"
    IRELAND = "104738515"
    SWITZERLAND = "106693272"
    LUXEMBOURG = "104042105"
    TURKEY = "102105699"
    NETHERLANDS = "102890719"
    GERMANY = "101282230"
    EUROPE = "91000000"
    UK = "101165590"


class LastTime(Enum):
    D = "r86400"
    W = "r604800"
    M = "r2592000"
    A = "no"


class LinkedInCrawler:
    __USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36"
    
    def __init__(self, profile_path):
        options = webdriver.ChromeOptions()
        options.add_argument(f"--user-data-dir={profile_path}")
        options.add_argument(f"--user-agent={self.__USER_AGENT}")
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(options=options)
        self.offset_increase = 25
        self.found_job_ids = set()

    def __get_search_url(self, keyword, location, page, time):
        search_url = f"https://www.linkedin.com/jobs/search?geoId={location}&keywords={keyword}&origin=JOB_SEARCH_PAGE_JOB_FILTER&start={page * self.offset_increase}"
        if time != LastTime.A.value:
            search_url += f"&f_TPR={time}"
        return search_url
    
    def __get_page_count(self):
        job_count_css_selector = ".jobs-search-results-list__subtitle"
        try:
            job_count_element = self.driver.find_element(By.CSS_SELECTOR, job_count_css_selector)
        except NoSuchElementException:
            return -1
        except WebDriverException:
            return -1
        job_count = int(job_count_element.text.replace(" results", "").replace(" result", "").replace(",", ""))
        return job_count // self.offset_increase
    
    def __search_and_wait(self, keyword, location, page = 0, time = LastTime.A.value):
        jobs_css_selector = ".scaffold-layout__list-detail-container"
        try:
            self.driver.get(self.__get_search_url(keyword, location, page, time))
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, jobs_css_selector)))
            sleep(1)
        except TimeoutException as e:
            print("can not change pages", e)
            sleep(10)
            return self.__search_and_wait(keyword, location, page, time)
        except (ReadTimeoutError, WebDriverException) as e:
            print("connection lost", e)
            sleep(10)
            return self.__search_and_wait(keyword, location, page, time)
        return True
            

    def __load_job_description_text(self, position, company_name):
        job_description_job_title_css_selector = ".job-details-jobs-unified-top-card__job-title"
        job_description_company_name_css_selector = ".job-details-jobs-unified-top-card__company-name"
        job_description_css_selector = "article"
        WebDriverWait(self.driver, 10).until(
            EC.all_of(
                EC.text_to_be_present_in_element((By.CSS_SELECTOR, job_description_job_title_css_selector), position),
                EC.text_to_be_present_in_element((By.CSS_SELECTOR, job_description_company_name_css_selector), company_name),
                ))
        return self.driver.find_element(By.CSS_SELECTOR, job_description_css_selector).text.lower()
    
    def __check_job(self, job, keyword, is_promoted_allowed, ignored_keywords, is_applied_allowed):
        try:
            sleep(0.5)
            job_text = job.text
            self.driver.execute_script("arguments[0].scrollIntoView()", job)
            job.click()
            job_summary = job_text.split("\n")
        except StaleElementReferenceException as e:
            print("job summary can not be found", e)
            return True
        except (WebDriverException, JavascriptException) as e:
            print("can not scroll to the job", e)
            return False
        if len(job_summary) == 1:
            print("Job summary length is 1. Maybe scroll problem", keyword, job_summary)
            return False
        position = job_summary[0]
        company_name = job_summary[2]
        location = job_summary[3]
        checked = True
        for ignored_keyword in ignored_keywords:
            if ignored_keyword in position:
                return True
        if "Applied" in job_summary and not is_applied_allowed:
            return True
        try:
            job_description_text = self.__load_job_description_text(position, company_name)
            checked = True
        except (TimeoutException, WebDriverException) as e:
            job_description_text = ""
            checked = False
            print("Job description timed out", e, position, company_name, job_summary)
        job_id = parse_qs(urlparse(self.driver.current_url).query).get("currentJobId", [None])[0]
        found_check = keyword in job_description_text and job_id is not None and job_id not in self.found_job_ids
        if not is_promoted_allowed:
            found_check = found_check and not "Promoted" in job_text
        if found_check:
            logger.info("New job found!", company_name=company_name, position=position, location=location, url=self.driver.current_url, keyword=keyword)
            self.found_job_ids.add(job_id)
        return checked

    def search(self, keyword, location, time, is_promoted_allowed, ignored_keywords, is_applied_allowed):
        print("Searching for ", keyword, location)
        location_val = Location[location].value
        time_val = LastTime[time].value
        print("Getting first page info")
        self.__search_and_wait(keyword, location_val, 0, time_val)
        print("Getting page count")
        page_count = self.__get_page_count()
        job_css_selector = ".scaffold-layout__list-item"
        page = 0
        while page <= page_count:
            print(page, page_count)
            jobs = self.driver.find_elements(By.CSS_SELECTOR, job_css_selector)
            for job in jobs:
                retry = 0
                while retry < 5:
                    print("Checking job", job)
                    if not self.__check_job(job, keyword, is_promoted_allowed, ignored_keywords, is_applied_allowed):
                        retry += 1
                    else:
                        break
            if page == page_count:
                print("Last page")
                break
            page += 1
            print("Wait for next page")
            self.__search_and_wait(keyword, location_val, page, time_val)
            new_page_count = self.__get_page_count()
            print("New page count ", new_page_count)
            if new_page_count == -1:
                break
            if new_page_count > page_count:
                page_count = new_page_count