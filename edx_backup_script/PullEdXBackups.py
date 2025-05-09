#!/usr/bin/env python3
# VPAL Multi-course Backup Script

import os
import csv
import sys
import time
import logging
import datetime
import argparse
import traceback
from getpass import getpass
from selenium.webdriver.chrome.webdriver import WebDriver as Chrome
from selenium.webdriver.firefox.webdriver import WebDriver as Firefox
from selenium.webdriver.safari.webdriver import WebDriver as Safari
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.common import exceptions as selenium_exceptions

# TODO: Better tracking of what we had to skip.

instructions = """
to run:
python3 PullEdXBackups.py filename.csv

The csv file must have these headers/columns:
Course - course name or identifier (optional)
URL - the address of class' outline page. It should look like this:
      https://course-authoring.edx.org/course/course-v1:HarvardX+CS109xa+3T2023

The output is another CSV file that shows which courses 
couldn't be accessed or downloaded.

Options:
  -h or --help:     Print this message and exit.
  -d or --download: Specify the download directory.
  -c or --chrome:   Use Chrome instead of default Firefox.
  -v or --visible:  Run the browser in normal mode instead of headless.

"""

# Prep the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.FileHandler("edx_backup.log")
formatter = logging.Formatter(
    "%(asctime)s : %(name)s  : %(funcName)s : %(levelname)s : %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)


# Just a faster thing to type and read.
def log(text, level="INFO"):
    print(text)
    if level == "DEBUG":
        logger.debug(text)
    if level == "INFO":
        logger.info(text)
    if level == "WARNING":
        logger.warning(text)
    if level == "ERROR":
        logger.error(text)
    if level == "CRITICAL":
        logger.critical(text)


def trimLog(log_file="edx_backup.log", max_lines=20000):
    """
    Trims a log file to a maximum number of lines.

    Parameters:
    log_file (str): The file to trim.
    max_lines (int): The maximum number of lines to keep.

    Returns:
    void

    """

    with open(log_file, "r") as f:
        lines = f.readlines()
    with open(log_file, "w") as f:
        f.writelines(lines[-max_lines:])


# Instantiating a headless Chrome or Firefox browser
def setUpWebdriver(run_headless, driver_choice, download_directory):
    log("Setting up webdriver.")
    os.environ["PATH"] = os.environ["PATH"] + os.pathsep + os.path.dirname(__file__)
    if download_directory is not None:
        full_destination = os.path.join("~/Downloads", download_directory)
        log("Setting download directory to " + full_destination)
        if not os.path.exists(full_destination):
            os.makedirs(full_destination)

    if driver_choice == "chrome":
        op = ChromeOptions()
        op.add_argument("start-maximized")
        if download_directory is not None:
            prefs = {"download.default_directory": full_destination}
            op.add_experimental_option("prefs", prefs)
        if run_headless:
            op.add_argument("--headless")
        driver = Chrome(options=op)
    elif driver_choice == "safari":
        op = SafariOptions()
        if run_headless:
            op.add_argument("--headless")
        driver = Safari(options=op)
    else:
        op = FirefoxOptions()
        if run_headless:
            op.headless = True
        if download_directory is not None:
            op.set_preference("browser.download.folderList", 2)
            op.set_preference("browser.download.dir", full_destination)
        driver = Firefox(options=op)

    driver.implicitly_wait(1)
    return driver


def signIn(driver, username, password):
    # Locations
    login_page = "https://authn.edx.org/login"
    username_input_css = "#emailOrUsername"
    password_input_css = "#password"
    login_button_css = "#sign-in"

    # Open the edX sign-in page
    log("Logging in...")
    driver.get(login_page)

    # Wait a second.
    time.sleep(1)

    # Apparently we have to run this more than once sometimes.
    login_count = 0
    while login_count < 3:
        # Sign in
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, username_input_css))
            )
        except selenium_exceptions.TimeoutException:
            driver.quit()
            sys.exit("Timed out waiting for username field.")

        # Wait a second.
        time.sleep(1)

        username_field = driver.find_elements(By.CSS_SELECTOR, username_input_css)[0]
        username_field.clear()
        username_field.send_keys(username)
        log("Username sent")

        # Wait a second.
        time.sleep(1)

        password_field = driver.find_elements(By.CSS_SELECTOR, password_input_css)[0]
        password_field.clear()
        password_field.send_keys(password)
        log("Password sent")

        # Wait a second.
        time.sleep(1)

        # Using ActionChains is necessary because edX put a div over the login button.
        login_button = driver.find_elements(By.CSS_SELECTOR, login_button_css)[0]
        actions = ActionChains(driver)
        actions.move_to_element(login_button).click().perform()
        log("Login button clicked")

        # Check to make sure we're signed in.
        # There are several possible fail states to check for.
        found_dashboard = False
        try:
            log("Finding dashboard...")
            found_dashboard = WebDriverWait(driver, 10).until(EC.url_contains("home"))
        except (
            selenium_exceptions.TimeoutException,
            selenium_exceptions.InvalidSessionIdException,
        ):
            log(traceback.print_exc(), "WARNING")
            login_fail = driver.find_elements(By.CSS_SELECTOR, "#login-failure-alert")
            if len(login_fail) > 0:
                log("Incorrect login or password")
            need_reset = driver.find_elements(
                By.CSS_SELECTOR, "#password-security-reset-password"
            )
            if len(need_reset) > 0:
                log("Password reset required")
            if "Forbidden" in driver.title:
                log("403: Forbidden")

        # If we're logged in, we're done.
        if found_dashboard:
            log("Logged in.")
            return

        login_count += 1
        log("Login attempt count: " + str(login_count))

    driver.close()
    log("Login failed.")
    sys.exit("Login issue or course dashboard page timed out.")


def getCourseExport(driver, url, last_url, download_directory):
    tools_menu_button_css = "#Tools-dropdown-menu"
    export_course_button_xpath = "//a[text()='Export Course']"
    make_export_button_xpath = "//button[text()='Export course content']"
    making_export_indicator_css = "div.course-stepper"
    download_export_button_xpath = "//a[text()='Download exported course']"
    wait_for_download_button = 100  # seconds

    # Apparently we have to open the course outline and go to the export page from there.
    # This is because edX broke things and didn't feel like fixing them.
    # Open the course outline.
    driver.get(url)
    try:
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, tools_menu_button_css))
        )

    except Exception as e:
        # If we can't open the URL, make a note, put the driver back,
        # and move on to the next url.
        log(repr(e), "DEBUG")
        log("Tools menu didn't load.")
        return False

    # Click the tools menu.
    tool_menu_button = driver.find_elements(By.CSS_SELECTOR, tools_menu_button_css)
    tool_menu_button[0].click()

    # Click the "export course" button.
    export_course_button = driver.find_elements(By.XPATH, export_course_button_xpath)
    export_course_button[0].click()

    log("Opening " + url)
    try:
        WebDriverWait(driver, 10).until(EC.url_changes(last_url))

    except Exception as e:
        # If we can't open the URL, make a note, put the driver back,
        # and move on to the next url.
        log(repr(e), "DEBUG")
        log("Webdriver didn't go anywhere.")
        return False

    # Now wait for the export button to appear.
    try:
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, make_export_button_xpath))
        )
    except Exception as e:
        # If we can't open the URL, make a note, put the driver back,
        # and move on to the next url.
        log(repr(e), "DEBUG")
        log("Export button did not appear.")
        return False

    # Click the "export course content" button.
    export_course_button = driver.find_elements(By.XPATH, make_export_button_xpath)
    export_course_button[0].click()
    log("Export button clicked")

    # Once it's clicked, this should appear:
    preparing_notice = driver.find_elements(
        By.CSS_SELECTOR, making_export_indicator_css
    )
    preparing_notice_visible = False
    # wait until it's visible
    try:
        preparing_notice_visible = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, making_export_indicator_css)
            )
        )
        log("EdX is preparing the export.")
    except Exception as e:
        log(repr(e), "DEBUG")
        log(making_export_indicator_css + " not visible.")

    # If it doesn't show up, click again up to 3 times.
    export_attempts = 1
    if not preparing_notice_visible:
        log("Export button did not work. Trying again.")
        log("Attempt #" + str(export_attempts))
        while export_attempts < 3:
            export_attempts += 1
            # Wait 3 seconds before clicking again.
            time.sleep(3)
            try:
                export_course_button[0].click()
                WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located(
                        (By.CSS_SELECTOR, making_export_indicator_css)
                    )
                )
            except Exception as e:
                log(repr(e), "DEBUG")

            preparing_notice = driver.find_elements(
                By.CSS_SELECTOR, making_export_indicator_css
            )
            if len(preparing_notice) > 0:
                break

    if len(preparing_notice) == 0:
        log("Export button did not work.")
        return False

    # Wait for the download button to appear.
    # For some reason we're not detecting it with visibility_of_element_located,
    # so we're just going to try to select it once a minute for 10 minutes.
    download_button_timer = 0
    max_download_tries = 10
    while download_button_timer < max_download_tries:
        log(str(download_button_timer) + " minutes elapsed.")
        time.sleep(60)
        download_course_button = driver.find_elements(
            By.XPATH, download_export_button_xpath
        )
        if len(download_course_button) > 0:
            break
        download_button_timer += 1

    if download_button_timer >= max_download_tries:
        log("Creation of course export timed out for " + url)
        return False

    # Download the file. Should go to the default folder.
    download_course_button[0].click()
    log("Downloading export from " + url)

    # Get the filename of the file I'm downloading.
    # Download link looks like this:
    # https://prod-edx-edxapp-import-export.s3.amazonaws.com/user_tasks/2023/04/06/course.zibb8idm.tar.gz?
    # AWSAccessKeyId=AKIAJ2Y2Z3ZQ

    download_url = download_course_button[0].get_attribute("href")
    downloaded_file = download_url.split("?")[0].split("/")[-1]

    # Wait until the file is downloaded.
    # TODO: Don't need to log, just need to wait.

    # Check once each second to see if the file is downloaded.
    timer = 0
    download_folder = os.path.join(os.path.expanduser("~"), "Downloads")
    if download_directory is not None:
        download_folder = os.path.join(download_folder, download_directory)
    while timer < wait_for_download_button:
        if os.path.isfile(os.path.join(download_folder, downloaded_file)):
            #  Rename the file to something useful.
            os.rename(
                os.path.join(download_folder, downloaded_file),
                os.path.join(
                    download_folder,
                    url.split("+")[1] + "_" + url.split("+")[2] + ".tar.gz",
                ),
            )
            break
        time.sleep(1)
        timer += 1

    # If the file is not downloaded, make a note and move on to the next url.
    if timer >= wait_for_download_button:
        log("Download timed out for " + url)
        return False

    log("Download complete from " + url)

    return True


#######################
# Main starts here
#######################


def PullEdXBackups():
    trimLog()

    num_classes = 0
    num_classes_downloaded = 0
    skipped_classes = []
    run_headless = True

    # Read in command line arguments.
    parser = argparse.ArgumentParser(usage=instructions, add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-v", "--visible", action="store_true")
    parser.add_argument("-c", "--chrome", action="store_true")
    parser.add_argument("-s", "--safari", action="store_true")
    parser.add_argument("-d", "--download", action="store", default=None)
    parser.add_argument("csvfile", default=None)

    args = parser.parse_args()
    if args.help or args.csvfile is None:
        sys.exit(instructions)

    if args.visible:
        run_headless = False

    driver_choice = "firefox"
    if args.chrome:
        log("Using Chrome instead of Firefox.")
        driver_choice = "chrome"
    if args.safari:
        log("Using Safari instead of Chrome.")
        driver_choice = "safari"

    if not os.path.exists(args.csvfile):
        sys.exit("Input file not found: " + args.csvfile)

    # Prompt for username and password
    # TODO: Maybe allow a file to read username and pw from.
    print(
        """
This script requires a username and password to run.
This user must have Admin status on all courses in which
the script is to run. Press control-C to cancel.
"""
    )
    username = input("User e-mail address: ")
    password = getpass()

    start_time = datetime.datetime.now()

    # Prep the web driver and sign into edX.
    driver = setUpWebdriver(run_headless, driver_choice, args.download)
    signIn(driver, username, password)

    # We have to open the Studio outline in order to avoid CORS issues for some reason.
    driver.get("https://studio.edx.org/home")
    # This redirects to https://course-authoring.edx.org/home , but we actually want to get the redirect!
    # When the input with id pgn-searchfield-input-1 shows up we're good to continue.
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "pgn-searchfield-input-1"))
        )
    except selenium_exceptions.TimeoutException:
        logger.error("Studio page load timed out.")
        driver.quit()
        sys.exit("Studio page load timed out.")

    # Open the csv and visit all the URLs.
    with open(args.csvfile, "r") as file:
        log("Opening csv file.")
        reader = csv.DictReader(file)
        last_url = ""
        for each_row in reader:
            url = each_row["URL"].strip()
            # Remove trailing slashes.
            url = url.rstrip("/")

            # Open the URL. Skip lines without one.
            if url == "":
                continue

            num_classes += 1
            if getCourseExport(driver, url, last_url, args.download):
                log("Downloaded " + url)
                num_classes_downloaded += 1
            else:
                log("Could not download " + url)
                skipped_classes.append(url)

            last_url = url

        # Done with the webdriver.
        # TODO: Wait for the last download to finish, and then quit.
        # It used to do that automatically, but no such luck now.
        """
        Get the filename from the download link. It'll have an href like this:
        https://prod-edx-edxapp-import-export.s3.amazonaws.com/user_tasks/2024/01/18/course.y2nltbo1.tar.gz?response-content-disposition=attachment%3B%20filename%3D%22course.y2nltbo1.tar.gz%22&response-content-encoding=application%2Foctet-stream&response-content-type=application%2Fx-tgz&AWSAccessKeyId=ASIA2KBJR2ON5UEQJT7L&Signature=jP%2FCN4jii0fRbriiJ8P5K4sckcA%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEPH%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJHMEUCIQC1IQw2c15zqccRkU4aGvDqwVzU%2F2N2L1zfkrWJIBZBFwIgcP6AwjC%2FDxgadnPy9ozLKPtJ0pyuRVAwhDtU4SfiJn0qsAUIShAAGgw3MDg3NTY3NTUzNTUiDIPQlQLewJwxQsZfvCqNBe6KUz%2BilNCJsxQ2cG5mwhbszClRJF8HY5DEZlhJHK2LinAzr3zEpwk%2BVqtkE64sCJGoMk4pK3oquHqzgQAdrOp2iJNDJNYkDUdwY%2B34bVgIdsLRzJh1vwvp3V618K2anmPqXNHGd%2Foec8WWE5eaK1k3KCw4QLi8r73cz67%2FCNcjIM0%2FcDgg69xNJZeOXEvDyInQ0s8mLbmBCNsLrp85eBkg0s2FJkf9KTTjEAi13eBV1vWJUyKHBWeruJmnE%2Fd5O3bJQi5qLkOG8FBJfD8rNhOENxGyyZEIO5DacVQV1L5pvqPKt1MrSLLDhg4HtG%2Fqz7Rd1nDD3DTM48SsOWsp7n6iq22D8ZngsvggGBAQ5UEf0BNWLei%2F5QknHuLFYPyW%2FaqxHRykJkafK0xIWDpd815SMIgmoT4jETOTChIQnX8%2Fuwh0xjRMypERuj%2BKXCfEwE%2Bviou8r7eQCEZx%2F8%2FTAoaAxqjjF14VgtgvGXNdr9UMspM%2FuMcaZkcfpw712t1%2BMvv0DsfriYSxagsXUeeDXuaL5wqgPQHcLFJxiuioja1ENGwR%2FTnCcumtQJcW%2BrVdW4N2cewx2WuX2NLbkqoaKvxpqFwGOD0%2FXmzQBMxvt4nVI6pM63YkB1NwKV1YnM4hMps3Fpx7kqmySWxycHdxEwpCrVyHgzPX7t2xF5sPawF0dbBlI%2BF05zyjJKAGfrIyJFR7h8T3wwUXLNelpEvpguOKy1xcWPgdOIJDc7SXY1XrnjCRSQc0b%2F1bUiwNaxrdno7VkBHxnMz5oTjqvGLMMdcx50ZFOxNnQNFS8REtYrZQmamCjgX5ste68IqYuWzHWKZZwVbl05sPDKNdOCKj2n3kVLqv3NL0%2FEcdEzvvMMfpybEGOrEBd%2FTrfxc5V3NYdhLvSI4d0QHsuJiFG%2FtIVdfrkKE5jwkyqEJTuSYUIoIxNveP27o6xVDsudUv6eYZC2tSAX%2BM0hRbUfZVqiVil0PJkT%2Frgh2JdjaTHfiC6G8gxKgQnff%2BJfSwbqvv9Nl%2BWDZZedAubKgBbn7pCyPBkFz2x5AQdR%2BvNsnCdz5sptT2Gf7AkQShJaIgb%2BPKxfxp4ObuThoiERQUx19xOzn%2BFlonZgUvKwwK&Expires=1715188555
        """
        driver.quit()

        # Write out a new csv with the ones we couldn't do.
        # TODO: sometimes driver.quit() doesn't work and we have to kill the process.
        # Should log the skipped classes to a file as we go instead of waiting.
        if len(skipped_classes) > 0:
            log("See remaining_courses.csv for courses that had to be skipped.")
            log(str(skipped_classes))
            with open("remaining_courses.csv", "w", newline="") as remaining_courses:
                fieldnames = ["URL"]
                writer = csv.DictWriter(
                    remaining_courses, fieldnames=fieldnames, extrasaction="ignore"
                )

                writer.writeheader()
                for x in skipped_classes:
                    writer.writerow({"URL": x})
        else:
            # Remove the remaining_courses.csv file if it exists.
            if os.path.exists("remaining_courses.csv"):
                os.remove("remaining_courses.csv")

        log("Processed " + str(num_classes - len(skipped_classes)) + " courses")
        end_time = datetime.datetime.now()
        log("in " + str(end_time - start_time).split(".")[0])

    # Done.


if __name__ == "__main__":
    PullEdXBackups()
