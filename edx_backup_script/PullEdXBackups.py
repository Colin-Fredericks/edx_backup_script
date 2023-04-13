#!/usr/bin/env python3
# VPAL Multi-course Backup Script

import os
import csv
import sys
import logging
import datetime
import argparse
import traceback
from getpass import getpass
from selenium import webdriver
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.common import exceptions as selenium_exceptions

# TODO: Better tracking of what we had to skip.

instructions = """
to run:
python3 PullEdXBackups.py filename.csv

The csv file must have these headers/columns:
Course - course name or identifier (optional)
URL - the address of class' export page. It should look like this:
      https://studio.edx.org/export/course-v1:HarvardX+CHEM160.en.1x+1T2018

The output is another CSV file that shows which courses 
couldn't be accessed or downloaded.

Options:
  -h or --help:    Print this message and exit.
  -f or --firefox: Use Firefox (geckodriver) instead of Chrome.
  -v or --visible: Run the browser in normal mode instead of headless.

"""

# Prep the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.FileHandler("edx_staffing.log")
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


def trimLog(log_file="edx_staffing.log", max_lines=20000):
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
def setUpWebdriver(run_headless, driver_choice):
    log("Setting up webdriver.")
    os.environ["PATH"] = os.environ["PATH"] + os.pathsep + os.path.dirname(__file__)
    if driver_choice == "firefox":
        op = FirefoxOptions()
        if run_headless:
            op.headless = True
        driver = webdriver.Firefox(options=op)
    else:
        op = ChromeOptions()
        op.add_argument("start-maximized")
        if run_headless:
            op.add_argument("--headless")
        driver = webdriver.Chrome(options=op)

    driver.implicitly_wait(1)
    return driver


# TODO: Do we actually need this for this script?
# Returns info about the dialog.
# If there was none, it's "no_dialog"
# If we closed it and they weren't a user, it's "no_user"
# If we couldn't close the dialog, it's "failed_to_close"
def closeErrorDialog(driver):

    # Try to find the "ok" button for the error dialogs.
    wrong_email_css = "#prompt-error.is-shown button.action-primary"
    wrong_email_ok_button = driver.find_elements(By.CSS_SELECTOR, wrong_email_css)

    # If there is an error dialog open, report why, clear it, and move on.
    if len(wrong_email_ok_button) > 0:
        log("error dialog open")
        try:
            # No user with specified e-mail address.
            wrong_email_ok_button[0].click()
            return {"reason": "no_user"}
        except Exception as e:
            # Couldn't close the error dialog.
            # log(repr(e), "DEBUG")
            log("Could not close error dialog for " + driver.title, "WARNING")
            return {"reason": "failed_to_close"}
    # If there's no error dialog, we were successful. Move on.
    else:
        # No error dialog
        return {"reason": "no_dialog"}


def signIn(driver, username, password):

    # Locations
    login_page = "https://authn.edx.org/login"
    username_input_css = "#emailOrUsername"
    user_button_css = "button#user"
    password_input_css = "#password"
    login_button_css = ".login-button-width"

    # Open the edX sign-in page
    log("Logging in...")
    driver.get(login_page)

    # Apparently we have to run this more than once sometimes.
    login_count = 0
    while login_count < 3:

        # Sign in
        try:
            found_username_field = WebDriverWait(driver, 100).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, username_input_css))
            )
        except selenium_exceptions.TimeoutException:
            driver.quit()
            sys.exit("Timed out waiting for username field.")

        username_field = driver.find_elements(By.CSS_SELECTOR, username_input_css)[0]
        username_field.clear()
        username_field.send_keys(username)
        log("Username sent")

        password_field = driver.find_elements(By.CSS_SELECTOR, password_input_css)[0]
        password_field.clear()
        password_field.send_keys(password)
        log("Password sent")

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
            found_dashboard = WebDriverWait(driver, 10).until(EC.title_contains("Home"))
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


def getCourseExport(driver, url, last_url):
    make_export_button_css = "a.action-export"
    download_export_button_css = "a#download-exported-button"
    wait_for_download_button = 600  # seconds

    # Open the URL. Wait until the browser's URL changes.
    log("Opening " + url)
    driver.get(url)
    try:
        WebDriverWait(driver, 10).until(
            EC.url_changes(last_url)
        )
    except Exception as e:
        # If we can't open the URL, make a note, put the driver back,
        # and move on to the next url.
        log(repr(e), "DEBUG")
        log("Webdriver didn't go anywhere.")
        return False

    # Now wait for the export button to appear.
    try:
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, make_export_button_css))
        )
    except Exception as e:
        # If we can't open the URL, make a note, put the driver back,
        # and move on to the next url.
        log(repr(e), "DEBUG")
        log("Export button did not appear.")
        return False

    # Click the "export course content" button.
    export_course_button = driver.find_elements(By.CSS_SELECTOR, make_export_button_css)
    export_course_button[0].click()

    try:
        WebDriverWait(driver, wait_for_download_button).until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, download_export_button_css)
            )
        )
    except:
        # If the download button never appears,
        # make a note and move on to the next url.
        log(repr(e), "DEBUG")
        log("Creation of course export timed out for " + url)
        return False

    # Download the file.
    download_course_button = driver.find_elements(
        By.CSS_SELECTOR, download_export_button_css
    )
    download_course_button[0].click()

    # Get the filename of the file I'm downloading.
    # Download link looks like this:
    # https://prod-edx-edxapp-import-export.s3.amazonaws.com/user_tasks/2023/04/06/course.zibb8idm.tar.gz?
    # AWSAccessKeyId=AKIAJ2Y2Z3ZQ
    
    # Wait until the file is downloaded.
    # TODO: What is my download location anyway?
    # TODO: Don't need to log, just need to wait.
    path = "path goes here"
    event_handler = LoggingEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path)
    observer.start()
    try:
        while observer.isAlive():
            observer.join(1)
    finally:
        observer.stop()
        observer.join()

    log("Downloading export from " + url)

    # Wait for the file to finish downloading.
    #   If it does, move on to the next url.
    #   If not, mark this one as a problem and put it on the list.
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
    timeouts = 0
    too_many_timeouts = 3

    # Read in command line arguments.
    parser = argparse.ArgumentParser(usage=instructions, add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-v", "--visible", action="store_true")
    parser.add_argument("-f", "--firefox", action="store_true")
    parser.add_argument("csvfile", default=None)

    args = parser.parse_args()
    if args.help or args.csvfile is None:
        sys.exit(instructions)

    if args.visible:
        run_headless = False

    if args.firefox:
        log("Using Firefox instead of Chrome.")
        driver_choice = "firefox"

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
    driver = setUpWebdriver(run_headless, driver_choice)
    signIn(driver, username, password)

    # Open the csv and visit all the URLs.
    with open(args.csvfile, "r") as file:

        log("Opening csv file.")
        reader = csv.DictReader(file)
        course_list = []
        for each_row in reader:
            url = each_row["URL"].strip()

            # Open the URL. Skip lines without one.
            if url == "":
                continue

            num_classes += 1
            log("Opening " + url)
            if getCourseExport(driver, url, last_url):
                log("Downloaded " + url)
                num_classes_downloaded += 1
            else:
                log("Could not download " + url)
                skipped_classes.append(url)

            last_url = url

        # Done with the webdriver.
        driver.quit()

        # Write out a new csv with the ones we couldn't do.
        if len(skipped_classes) > 0:
            log("See remaining_courses.csv for courses that had to be skipped.")
            with open("remaining_courses.csv", "w", newline="") as remaining_courses:
                fieldnames = ["Course", "URL", "Add", "Promote", "Remove", "Demote"]
                writer = csv.DictWriter(
                    remaining_courses, fieldnames=fieldnames, extrasaction="ignore"
                )

                writer.writeheader()
                for x in skipped_classes:
                    writer.writerow(x)

        log("Processed " + str(num_classes - len(skipped_classes)) + " courses")
        end_time = datetime.datetime.now()
        log("in " + str(end_time - start_time).split(".")[0])

    # Done.


if __name__ == "__main__":
    PullEdXBackups()
