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
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common import exceptions as selenium_exceptions
from selenium.webdriver.support import expected_conditions as EC

# TODO: Better tracking of what we had to skip.

instructions = """
to run:
python3 ReplaceEdXStaff.py filename.csv

The csv file must have these headers/columns:
Course - course name or identifier (optional)
URL - the address of class' Course Team Settings page
Add - the e-mail addresses of the staff to be added. (not usernames)
      If there are multiple staff, space-separate them.
Promote - promote these people to Admin status
Remove - just like "Add"
Demote - removes Admin status

The output is another CSV file that shows which courses couldn't be accessed
and which people couldn't be removed. If the --list option is used,
the CSV instead shows who's admin and staff in all courses.

Options:
  -h or --help:    Print this message and exit.
  -l or --list:    List all staff and admin in all courses. Make no changes.
                   Only requires the URL column.
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


# Instantiating a headless Chrome browser
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
        # First, check to see if we're still on the same page, a common fail state.

        """
        log("Waiting for URL change...")
        try:
            url_change = WebDriverWait(driver, 15).until(
                EC.url_changes(driver.current_url)
            )
        except selenium_exceptions.TimeoutException:
            log("URL didn't change. Trying again.", "WARNING")
            login_count += 1
            print("Login attempt count: " + str(login_count))
            continue
        """
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


def getCourseExport(driver, url):
    make_export_button_css = "a.action-export"
    download_export_button_css = "a#download-exported-button"
    wait_for_download_button = 600  # seconds

    # Open the URL
    try:
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, make_export_button_css))
        )
    except Exception as e:
        # If we can't open the URL, make a note, put the driver back,
        # and move on to the next url.
        log(repr(e), "DEBUG")
        log("Couldn't open " + url)
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
        # make a note, put the driver back, and move on to the next url.
        log(repr(e), "DEBUG")
        log("Timed out on " + url)
        return False

    # Wait to see if the export processes.
    #   If it does, download the file.
    download_course_button = driver.find_elements(
        By.CSS_SELECTOR, download_export_button_css
    )
    download_course_button[0].click()
    #   If not, mark this one as a problem and put it on the list.

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
    num_classes_fixed = 0
    skipped_classes = []
    staffed_classes = []
    unfound_addresses = []
    run_headless = True
    timeouts = 0
    too_many_timeouts = 3

    # Read in command line arguments.
    parser = argparse.ArgumentParser(usage=instructions, add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-l", "--list", action="store_true")
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

    # Open the csv and read it to a set of dicts
    with open(args.csvfile, "r") as file:

        log("Opening csv file.")
        reader = csv.DictReader(file)

        # For each line in the CSV...
        for each_row in reader:
            # log("Processing line:", "DEBUG")
            # log(each_row, "DEBUG")
            url = "https://studio.edx.org/export/" + each_row["course_id"].strip()

            # Open the URL. Skip lines without one.
            if url == "":
                continue

            num_classes += 1
            log("Opening " + url)
            getCourseExport(
                driver, url
            )

            # Check to make sure we've opened a new page.
            # The e-mail input box should be invisible.
            try:
                WebDriverWait(driver, 10).until(
                    EC.invisibility_of_element_located(
                        (By.CSS_SELECTOR, "input#user-email-input")
                    )
                )
                timeouts = 0
            except Exception as e:
                # log(repr(e), "DEBUG")
                # If we can't open the URL, make a note and skip this course.
                skipped_classes.append(each_row)
                if "Dashboard" in driver.title:
                    log("Course Team page load timed out for " + each_row["URL"])
                    skipped_classes.append(each_row)
                    timeouts += 1
                    if timeouts >= too_many_timeouts:
                        log(
                            str(too_many_timeouts)
                            + " course pages timed out in a row.",
                            "WARNING",
                        )
                        log(
                            "Check URLs and internet connectivity and try again.",
                            "WARNING",
                        )
                        break
                continue

            # If we only need to get users and status, we can do that easier.
            if args.list:
                log("Getting staff for " + each_row["Course"])
                # log(user_list)
                this_class = {
                    "Course": each_row["Course"],
                    "URL": url
                }
                staffed_classes.append(this_class)
                continue


            if (
                "Export" not in driver.title
                or "Forbidden" in driver.title
            ):
                log("\nCould not open course " + url)
                skipped_classes.append(each_row)
                continue

            log("\n" + driver.title)
            log(url)
            getCourseExport(driver, url)

        # Done with the webdriver.
        driver.quit()

        # Write out a new csv with the ones we couldn't do.
        if len(skipped_classes) > 0:
            log("See remaining_courses.csv for courses that had to be skipped.")
            with open(
                "remaining_courses.csv", "w", newline=""
            ) as remaining_courses:
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
