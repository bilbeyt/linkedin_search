import argparse
from crawler import LinkedInCrawler, Location, LastTime


if __name__ == "__main__":
    keywords = []
    locations = [l.name for l in Location]
    times = [t.name for t in LastTime]
    ignored_keywords = []
    parser = argparse.ArgumentParser(
        prog="Linkedin search engine", 
        description="real search for Linkedin")
    parser.add_argument("--profile-path", type=str, help="chrome profile path")
    parser.add_argument("--location", nargs="+", type=str, help="location to search for", choices=locations, default=locations)
    parser.add_argument("--keyword", nargs="+", type=str, help="what to search for like python, django", default=keywords)
    parser.add_argument("--promoted-allowed", default=False, action="store_true")
    parser.add_argument("--applied-allowed", default=False, action="store_true")
    parser.add_argument("--time", help="date ago to search for", type=str, choices=times, default=LastTime.D.name)
    parser.add_argument("--ignored-keywords", nargs="+", type=str, help="keywords to ignore on job title", default=ignored_keywords)
    parsed_args = parser.parse_args()
    crawler = LinkedInCrawler(parsed_args.profile_path)
    print("Starting")
    for location in parsed_args.location:
        for keyword in parsed_args.keyword:
            crawler.search(keyword, location, parsed_args.time, parsed_args.promoted_allowed, parsed_args.ignored_keywords, parsed_args.applied_allowed)
    print("Finished")