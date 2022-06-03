#!/usr/bin/env python3
# VPAL Backup Script for edX Courses

import os
import csv
import sys
import time
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

# TODO: Rename the export files to useful things.

all_drivers = {}

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
def setUpWebdriver(run_headless, target_folder):
    log("Setting up webdriver.")
    os.environ["PATH"] = os.environ["PATH"] + os.pathsep + os.path.dirname(__file__)
    op = Options()
    if run_headless:
        op.add_argument("--headless")
    op.add_experimental_option(
        "prefs",
        {
            "download.default_directory": target_folder,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing_for_trusted_sources_enabled": False,
            "safebrowsing.enabled": False,
        },
    )
    driver = webdriver.Chrome(options=op)
    driver.implicitly_wait(5)

    # Other potential downloady things:
    # https://stackoverflow.com/questions/57599776/download-file-through-google-chrome-in-headless-mode
    # options = Options()
    # options.add_argument("--headless")
    # options.add_argument("--start-maximized")
    # options.add_argument("--no-sandbox")
    # options.add_argument("--disable-extensions")
    # options.add_argument('--disable-dev-shm-usage')
    # options.add_argument("--disable-gpu")
    # options.add_argument('--disable-software-rasterizer')
    # options.add_argument("user-agent=Mozilla/5.0 (Windows Phone 10.0; Android 4.2.1; Microsoft; Lumia 640 XL LTE) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Mobile Safari/537.36 Edge/12.10166")
    # options.add_argument("--disable-notifications")
    #
    # options.add_experimental_option("prefs", {
    #     "download.default_directory": "C:\\link\\to\\folder",
    #     "download.prompt_for_download": False,
    #     "download.directory_upgrade": True,
    #     "safebrowsing_for_trusted_sources_enabled": False,
    #     "safebrowsing.enabled": False
    #     }
    # )
    #
    # Allow headless browsers to download things.
    # Code from https://stackoverflow.com/questions/52830115/python-selenium-headless-download
    # driver.command_executor._commands["send_command"] = (
    #     "POST",
    #     "/session/$sessionId/chromium/send_command",
    # )
    # params = {
    #     "cmd": "Page.setDownloadBehavior",
    #     "params": {"behavior": "allow", "downloadPath": target_folder},
    # }
    # driver.execute("send_command", params)

    return driver


def signIn(id, username, password):

    # Locations
    login_page = "https://authn.edx.org/login"
    username_input_css = "#emailOrUsername"
    password_input_css = "#password"
    login_button_css = ".login-button-width"

    # Open the edX sign-in page
    log("Logging in...")
    all_drivers[id].get(login_page)

    # Sign in
    username_field = all_drivers[id].find_elements(By.CSS_SELECTOR, username_input_css)[
        0
    ]
    username_field.clear()
    username_field.send_keys(username)
    password_field = all_drivers[id].find_elements(By.CSS_SELECTOR, password_input_css)[
        0
    ]
    password_field.clear()
    password_field.send_keys(password)
    login_button = all_drivers[id].find_elements(By.CSS_SELECTOR, login_button_css)[0]
    login_button.click()

    # Check to make sure we're signed in
    try:
        found_dashboard = WebDriverWait(all_drivers[id], 10).until(
            EC.title_contains("Dashboard")
        )
    except:
        driver.close()
        if "Forbidden" in all_drivers[id].title:
            sys.exit("403: Forbidden")
        if "Login" in all_drivers[id].title:
            sys.exit("Took too long to log in.")
        sys.exit("Could not log into edX or course dashboard page timed out.")

    log("Logged in.")


def signInAll(ids, username, password, return_list):

    while not ids.empty():
        id = ids.get()
        print("id: " + str(id))
        print("all drivers: " + str(all_drivers))
        print("this driver: " + str(all_drivers[id]))
        signIn(id, username, password)
        return_list.append(id)
    return return_list


# Runs the loop that processes things.
def getDownloads(ids, urls, failed_courses):

    print("Getting downloads")

    make_export_button_css = "a.action-export"
    download_export_button_css = "a#download-exported-button"
    wait_for_download_button = 600  # seconds

    # As long as we still have URLs to process,
    while not urls.empty():
        # Pull a URL and driver off their queues.
        url = urls.get()
        id = ids.get()
        print("Starting work on " + url)

        # Open the URL
        try:
            WebDriverWait(all_drivers[id], 10).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, make_export_button_css)
                )
            )
        except Exception as e:
            # If we can't open the URL, make a note, put the driver back,
            # and move on to the next url.
            log(repr(e), "DEBUG")
            log("Couldn't open " + url)
            failed_courses.append(url)
            ids.put(id)
            continue

        # Click the "export course content" button.
        export_course_button = all_drivers[id].find_elements(
            By.CSS_SELECTOR, make_export_button_css
        )
        export_course_button[0].click()

        try:
            WebDriverWait(d, wait_for_download_button).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, download_export_button_css)
                )
            )
        except:
            # If the download button never appears,
            # make a note, put the driver back, and move on to the next url.
            log(repr(e), "DEBUG")
            log("Timed out on " + url)
            failed_courses.append(url)
            ids.put(id)
            continue

        # Wait to see if the export processes.
        #   If it does, download the file.
        download_course_button = all_drivers[id].find_elements(
            By.CSS_SELECTOR, download_export_button_css
        )
        download_course_button[0].click()
        #   If not, mark this one as a problem and put it on the list.

        print("Downloading export from " + url)

        # When the webdriver is ready again, put it back on its queue.
        ids.put(id)

    print("URL queue empty.")
    # Shut down all the webdrivers.
    # TODO: DON'T SHUT DOWN IF THERE'S STILL STUFF DOWNLOADING.
    # Do we just want to wait 5 minutes or something? Not the best approach.
    # Get filename from download link? It's in the href buried in
    # %20filename%3D%22course.(identifier).tar.gz%22&amp; , doesn't seem super-stable.
    for i in iter(ids.get, None):
        all_drivers[i].quit()

    return True


def readArgs():
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

    #  If there's no output folder specified, use the working directory.
    if args.output:
        if not os.path.exists(args.output):
            sys.exit("Output folder not found: " + args.output)
        else:
            target_folder = args.output
    else:
        target_folder = os.getcwd()

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

    return target_folder, simultaneous_sessions, run_headless, args.csvfile


# Open the csv and read the URLs into our queue.
def makeURLQueue(csvfile):
    urls = multiprocessing.Queue()
    with open(csvfile, "r") as f:
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


def PullEdXBackups():

    global all_drivers
    num_classes = 0
    num_backups_successful = 0
    skipped_classes = []
    run_headless = True
    simultaneous_sessions = 2
    # TODO: replace with max(multiprocessing.cpu_count() - 2, 1)

    target_folder, simultaneous_sessions, run_headless, csvfile = readArgs()

    # Open the csv and read the URLs into a multiprocessing queue.
    urls = makeURLQueue(csvfile)

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

    # Multiprocessing requires "pickling" the objects you send it.
    # You can't pickle webdrivers, so we're tracking them by ID here.
    driver_id_queue = multiprocessing.Queue()
    driver_ids = list(range(simultaneous_sessions))
    for id in driver_ids:
        driver_id_queue.put(id)
    all_drivers = {i: setUpWebdriver(run_headless, target_folder) for i in driver_ids}
    print(str(all_drivers))

    # Sign in all the webdrivers
    # Need Manager to keep track of them so we can requeue them.
    login_manager = multiprocessing.Manager()
    return_list = login_manager.list()
    sign_in_jobs = []
    for i in range(0, simultaneous_sessions):
        # Creating processes that will run in parallel.
        p = multiprocessing.Process(
            target=signInAll,
            args=(driver_id_queue, username, password, return_list),
        )
        # Track them so we can stop them later.
        sign_in_jobs.append(p)
        # Run the processes.
        p.start()
    for x in sign_in_jobs:
        # Closes out the processes cleanly.
        x.join()

    # Now that the drivers are signed in we need to put them back in the queue.
    for id in return_list:
        driver_ids.put(id)

    # Run the download processes.
    # Using a Manager to keep track of which ones failed.
    fail_manager = multiprocessing.Manager()
    failed_courses = fail_manager.list()
    processes = []
    for n in range(0, simultaneous_sessions):
        # Creating processes that will run in parallel.
        p = multiprocessing.Process(
            target=getDownloads,
            args=(driver_id_queue, urls, failed_courses),
        )
        # Track them so we can stop them later.
        processes.append(p)
        # Run the processes.
        p.start()
    for x in processes:
        # Closes out the processes cleanly.
        x.join()

    # print(failed_courses)
    # log("Processed " + str(num_classes - len(skipped_classes)) + " courses")
    end_time = datetime.datetime.now()
    log("in " + str(end_time - start_time).split(".")[0])


if __name__ == "__main__":
    PullEdXBackups()
