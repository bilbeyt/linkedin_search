# linkedin_search

This project is making LinkedIn searches easy. It is scanning job description with your keyword
and if it is there it is storing it until the end and giving you the report.

## Usage

1. Add chromedriver to the root folder.
2. Go to `chrome://version/` to learn about your `Profile Path`
3. Use `--profile-path` flag to set your profile path.
4. Install dependencies by `pip install -r requirements.txt`
5. Login to your linkedin account with your default profile.
6. Run the app via `python app.py --profile-path=${PROFILE_PATH}`
