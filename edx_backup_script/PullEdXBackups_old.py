#!/usr/bin/env python3
# VPAL Backup Script for edX Courses

import os
import csv
import sys
import time
import logging
import datetime
import argparse
from getpass import getpass
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
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
and which people couldn't be removed.
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


# Instantiating a headless Chrome browser
def setUpWebdriver(run_headless):
    log("Setting up webdriver.")
    os.environ["PATH"] = os.environ["PATH"] + os.pathsep + os.path.dirname(__file__)
    op = Options()
    if run_headless:
        op.add_argument("--headless")
    driver = webdriver.Chrome(options=op)
    driver.implicitly_wait(1)
    return driver


def userIsPresent(driver, email):
    user_present_css = "li[data-email='" + email.lower() + "']"
    user_present = driver.find_elements(By.CSS_SELECTOR, user_present_css)
    if len(user_present) > 0:
        return True
    else:
        return False


def userIsStaff(driver, email):
    staff_user_css = "li[data-email='" + email.lower() + "'] span.flag-role-staff"
    staff_flag = driver.find_elements(By.CSS_SELECTOR, staff_user_css)
    if len(staff_flag) > 0:
        return True
    else:
        return False


def userIsAdmin(driver, email):
    admin_user_css = "li[data-email='" + email.lower() + "'] span.flag-role-instructor"
    admin_flag = driver.find_elements(By.CSS_SELECTOR, admin_user_css)
    if len(admin_flag) > 0:
        return True
    else:
        return False


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
    password_input_css = "#password"
    login_button_css = ".login-button-width"

    # Open the edX sign-in page
    log("Logging in...")
    driver.get(login_page)

    # Sign in
    username_field = driver.find_elements(By.CSS_SELECTOR, username_input_css)[0]
    username_field.clear()
    username_field.send_keys(username)
    password_field = driver.find_elements(By.CSS_SELECTOR, password_input_css)[0]
    password_field.clear()
    password_field.send_keys(password)
    login_button = driver.find_elements(By.CSS_SELECTOR, login_button_css)[0]
    login_button.click()

    # Check to make sure we're signed in
    try:
        found_dashboard = WebDriverWait(driver, 10).until(
            EC.title_contains("Dashboard")
        )
    except:
        driver.close()
        if "Forbidden" in driver.title:
            sys.exit("403: Forbidden")
        if "Login" in driver.title:
            sys.exit("Took too long to log in.")
        sys.exit("Could not log into edX or course dashboard page timed out.")

    log("Logged in.")
    return


def addStaff(driver, email_list):

    # Locations for add-staff inputs
    new_team_css = "a.create-user-button"
    new_staff_email_css = "input#user-email-input"
    add_user_css = "div.actions button.action-primary"

    # For each address:
    for email in email_list:
        success = False

        # If the user is already present, move to the next e-mail address.
        if userIsPresent(driver, email):
            log(email + " is already on course team.")
            continue

        # Retry up to 3 times.
        for x in range(0, 3):
            log("Trying to add " + email)

            try:
                # Click the "New Team Member" button
                new_team_buttons = driver.find_elements(By.CSS_SELECTOR, new_team_css)
                new_team_buttons[0].click()
            except Exception as e:
                # If that failed, there could be an error message up. Try to close it.
                closeErrorDialog(driver)

            try:
                # Put the e-mail into the input box.
                email_boxes = driver.find_elements(By.CSS_SELECTOR, new_staff_email_css)
                email_boxes[0].clear()
                email_boxes[0].send_keys(email)
                # Click "Add User"
                add_user_buttons = driver.find_elements(By.CSS_SELECTOR, add_user_css)
                add_user_buttons[0].click()

                # Now that we've clicked the add button,
                # Either the user was added or there's an error dialog.
                if userIsPresent(driver, email):
                    # All good.
                    success = True
                    break
                else:
                    # Clear the dialog and move on to the next e-mail.
                    closeErrorDialog(driver)
                    break

            except Exception as e:
                # If the stuff above failed, it's probably because
                # one of the elements hasn't been added to the page yet.
                log("Couldn't add " + email + ", trying again...")
                # log(repr(e), "DEBUG")

        if success:
            log("Added " + email)
        else:
            log("Could not add " + email)
            closeErrorDialog(driver)

    return


def promoteStaff(driver, email_list):

    # For each address:
    for email in email_list:

        success = False
        promotion_css = (
            "li[data-email='"
            + email.lower()
            + "'] a.make-instructor.admin-role.add-admin-role"
        )

        if userIsStaff(driver, email):

            # Keep trying up to 3 times in case we're still loading.
            for x in range(0, 3):
                log("Promoting " + email)
                try:
                    # Find the promotion button for this user.
                    promotion_button = driver.find_elements(
                        By.CSS_SELECTOR, promotion_css
                    )
                except:
                    log(
                        "No promotion button found. You may not have Admin access. Trying again...",
                        "WARNING",
                    )
                    continue
                try:
                    promotion_button[0].click()
                    success = True
                    break
                except Exception as e:
                    # log(repr(e), "DEBUG")
                    log("Couldn't click promotion button. Trying again...")
        else:
            if userIsAdmin(driver, email):
                log(email + " is already admin.")
            else:
                log(email + " is not in this course. Add them before promoting them.")

        if success:
            log("Promoted " + email + " to Admin.")
        else:
            log("Could not promote " + email)

    return


def removeStaff(driver, email_list):

    # The "remove" button is a link inside an LI.
    # The LI has data-email equal to the user's email address.
    trash_can_css = "a.remove-user"
    confirm_removal_css = "#prompt-warning.is-shown button.action-primary"

    # For each address:
    for email in email_list:

        # If this user isn't present, move on to the next one.
        if not userIsPresent(driver, email):
            log(email + " was already not in this course.")
            continue

        success = False
        removal_button_css = "li[data-email='" + email.lower() + "'] " + trash_can_css

        for x in range(0, 3):
            try:
                # E-mail addresses in the data attribute are lowercased.
                remove_button = driver.find_elements(
                    By.CSS_SELECTOR, removal_button_css
                )
                # Click the trash can ("remove user" button)
                remove_button[0].click()
                # Click the "confirm" button.
                log("Trying to remove " + email)
                confirm_button = driver.find_elements(
                    By.CSS_SELECTOR, confirm_removal_css
                )
                confirm_button[0].click()
                success = True
                break

            except Exception as e:
                # log(repr(e), "DEBUG")
                # Keep trying up to 3 times.
                log("Trying again...")

        if success:
            log("Removed " + email)
        else:
            log("Could not remove " + email)

    return


def demoteStaff(driver, email_list):

    # For each address:
    for email in email_list:

        success = False
        demotion_css = (
            "li[data-email='"
            + email.lower()
            + "'] a.make-staff.admin-role.remove-admin-role"
        )

        if userIsAdmin(driver, email):

            # Keep trying up to 3 times in case we're still loading.
            for x in range(0, 3):
                log("Demoting " + email)
                try:
                    # Find the demotion button for this user.
                    demotion_button = driver.find_elements(
                        By.CSS_SELECTOR, demotion_css
                    )
                except:
                    log(
                        "Couldn't find demotion button. You may not have Admin access. Trying again...",
                        "WARNING",
                    )
                    continue
                try:
                    demotion_button[0].click()
                    success = True
                    break
                except Exception as e:
                    # log(repr(e), "DEBUG")
                    log("Couldn't click demotion button. Trying again...")
        else:
            if userIsStaff(driver, email):
                log(email + " is already staff.")
            else:
                log(email + " is not in this course.")

        if success:
            log("Demoted " + email + " to staff.")
        else:
            log("Could not demote " + email)

    return


#######################
# Main starts here
#######################


def PullEdXBackups():

    num_classes = 0
    num_backups_successful = 0
    skipped_classes = []
    simultaneous_downloads = 5
    sessions = []
    run_headless = True
    timeouts = 0
    too_many_timeouts = 3

    # Read in command line arguments.
    parser = argparse.ArgumentParser(usage=instructions, add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-v", "--visible", action="store_true")
    parser.add_argument("-o", "--output", action="store")
    parser.add_argument("-s", "--sessions", action="store")
    parser.add_argument("csvfile", default=None)

    args = parser.parse_args()
    if args.help or args.csvfile is None:
        sys.exit(instructions)

    if args.visible:
        run_headless = False

    if args.sessions:
        simultaneous_downloads = int(args.sessions)

    if not os.path.exists(args.csvfile):
        sys.exit("Input file not found: " + args.csvfile)

    if not os.path.exists(args.output):
        sys.exit("Output folder not found: " + args.output)

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

    # Get a list of dicts from the CSV file.
    # { "URL": export page URL,
    #   "checked_out": have we started on this one? (bool),
    #   "completed": did we successfully get the download? (bool),
    #   "failed": or did it fail for some reason?  (bool)}

    course_list = []
    completed_URLs = []
    failed_URLs = []
    each_course = {"URL": "", "checked_out": False, "completed": False, "failed": False}

    # Open the text file and fill out the course list.

    # Because course exports can take a long time, we're going to
    # run multiple of them simultaneously. Spin up N webdrivers and log them in.
    # TODO: Rework this to be asynchronous.
    for i in range(0, simultaneous_downloads):
        session[i] = setUpWebdriver(run_headless)
        signIn(session[i], username, password)

    courses_left = len(course_list)
    drivers_available = simultaneous_downloads

    # While there are URLs left to visit:
    #   Check to see if there's an available webdriver.
    #   If there is:
    #       Mark that driver as unavailable.
    #       Send that driver and a URL to an asynch worker.
    #       When it's done,
    #           mark that driver as available
    #           move the URL to the "complete" or "failed" list.

    #################
    # Old Stuff
    #################

    # Open the csv and read it to a set of dicts
    with open(args.csvfile, "r") as file:
        log("Opening csv file.")
        reader = csv.DictReader(file)

        # For each line in the CSV...
        for each_row in reader:
            # log("Processing line:", "DEBUG")
            # log(each_row, "DEBUG")

            # Open the URL. Skip lines without one.
            if each_row["URL"] == "":
                continue

            num_classes += 1
            driver.get(each_row["URL"].strip())

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

            # Check to make sure we have the ability to change user status.
            if not userIsAdmin(driver, username):
                log("\nUser is not admin in " + each_row["URL"])
                skipped_classes.append(each_row)
                continue

            if (
                "Course Team Settings" not in driver.title
                or "Forbidden" in driver.title
            ):
                log("\nCould not open course " + each_row["URL"])
                skipped_classes.append(each_row)
                continue

            log("\n" + driver.title)
            log(each_row["URL"])
            # Functions to call for each task. As of Python 3.6 they'll stay in this order.
            jobs = {
                "Add": addStaff,
                "Promote": promoteStaff,
                "Remove": removeStaff,
                "Demote": demoteStaff,
            }
            for j in jobs:
                if each_row[j] is None:
                    driver.quit()
                    log("CSV error - might be missing a column.", "CRITICAL")
                    continue
                # Taking out whitespace.
                # Split e-mail list on spaces and throw out blank elements.
                email_list_with_blanks = each_row[j].split(" ")
                email_list = [x for x in email_list_with_blanks if x != ""]
                if len(each_row[j]) > 0:
                    jobs[j](driver, email_list)
                    # You have to wait because I don't even know why.
                    # Otherwise it skips lines - sometimes up to half of them.
                    time.sleep(2)

        # Done with the webdriver.
        driver.quit()

        # Write out a new csv with the ones we couldn't do.
        if len(skipped_classes) > 0:
            log("See remaining_courses.csv for courses that had to be skipped.")
            with open("remaining_courses.csv", "w", newline="") as remaining_courses:
                fieldnames = ["Course", "URL", "Add", "Promote", "Remove", "Demote"]
                writer = csv.DictWriter(remaining_courses, fieldnames=fieldnames)

                writer.writeheader()
                for x in skipped_classes:
                    writer.writerow(x)

        log("Processed " + str(num_classes - len(skipped_classes)) + " courses")
        end_time = datetime.datetime.now()
        log("in " + str(end_time - start_time).split(".")[0])

    # Done.


if __name__ == "__main__":
    PullEdXBackups()
