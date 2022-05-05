#!/usr/bin/env python3
# VPAL Backup Script for edX Courses

import os
import csv
import sys
import time
import random
import logging
import datetime
import argparse
import multiprocessing
from getpass import getpass
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

instructions = """
to run:
python3 PullEdXBackups.py (options) filename.csv

This script accesses multiple courses' Export pages
to download .tar.gz files for backup purposes.

The csv file only needs one header:
URL - the address of class' Export page

Options:
-h, --help     Print this message and exit.
-o, --output   Sets the folder where the course exports will be saved.
               Defaults to the current directory.
-s, -sessions  Sets the number of simultaneous sessions.
               Minimum 1, max and default of CPU count - 1.
-v, --visible  Runs the browser in regular mode instead of headless.

This script also creates a second CSV file, missing_exports.csv,
which shows which courses couldn't be accessed.
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


def signInAll(drivers, username, password):
    while not drivers.empty():
        d = drivers.get()
        signIn(d, username, password)
    return d


# Runs the loop that processes things.
# In this example it just waits a random amount of time,
# to simulate projects taking different amounts of time.
def getDownloads(drivers, urls):

    # As long as there's something in the input queue,
    while not inputs.empty():
        # Pull an input and tool off their queues.
        i = inputs.get()
        t = tools.get()
        print("Tool " + t + " starting work on " + str(i))
        # "process" the data (just waiting)
        time.sleep(random.randint(5, 10))
        print("Tool " + t + " finished work on " + str(i))
        # When the tool is ready again, put it back on its queue.
        tools.put(t)
    print("queue empty")
    return True


def PullEdXBackups():

    num_classes = 0
    num_backups_successful = 0
    skipped_classes = []
    simultaneous_sessions = multiprocessing.cpu_count() - 1
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

    if not os.path.exists(args.csvfile):
        sys.exit("Input file not found: " + args.csvfile)

    if args.output:
        if not os.path.exists(args.output):
            sys.exit("Output folder not found: " + args.output)

    if args.visible:
        run_headless = False

    # Spin up several processes, but not more than we have tools.
    # Leave some CPU for other people.
    if args.sessions:
        try:
            simultaneous_sessions = int(args.sessions)
        except:
            sys.exit("Are you sure you entered a number for the number of sessions?")
    else:
        simultaneous_sessions = max(1, simultaneous_sessions)
    print("Running with " + str(simultaneous_sessions) + " sessions.")

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

    # Read the CSV.

    # Open the csv and read the URLs into our queue.
    urls = multiprocessing.Queue()
    with open(args.csvfile, "r") as f:
        log("Opening csv file.")
        reader = csv.DictReader(f)

        # For each line in the CSV...
        for each_row in reader:
            # log("Processing line:", "DEBUG")
            # log(each_row, "DEBUG")

            # Open the URL. Skip lines without one.
            if each_row["URL"] == "":
                continue

            urls.put(each_row["URL"])

    # These are the webdrivers that process our downloads.
    drivers = multiprocessing.Queue()
    for j in range(0, simultaneous_sessions):
        drivers.put(setUpWebdriver(run_headless))

    # Sign in all the webdrivers
    # Need to keep track of them so we can requeue them.
    manager = multiprocessing.Manager()
    return_list = manager.list()
    sign_ins = []
    for i in range(0, simultaneous_sessions):
        # Creating processes that will run in parallel.
        p = multiprocessing.Process(
            target=signInAll,
            args=(drivers, username, password, return_list),
        )
        # Track them so we can stop them later.
        sign_ins.append(p)
        # Run the processes.
        p.start()
    for x in sign_ins:
        # Closes out the processes cleanly.
        x.join()

    # Now that they're signed in we need to put them back in the queue.
    for j in range(0, simultaneous_sessions):
        drivers.put(return_list[j])

    # Run the download processes.
    processes = []
    for n in range(0, simultaneous_sessions):
        # Creating processes that will run in parallel.
        p = multiprocessing.Process(
            target=getDownloads,
            args=(
                drivers,
                urls,
            ),
        )
        # Track them so we can stop them later.
        processes.append(p)
        # Run the processes.
        p.start()
    for x in processes:
        # Closes out the processes cleanly.
        x.join()


if __name__ == "__main__":
    PullEdXBackups()
