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
-h or --help: Print this message and exit.
-o or --output: Sets the folder where the course exports will be saved.
                Defaults to the current directory.

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


# Runs the loop that processes things.
# In this example it just waits a random amount of time,
# to simulate projects taking different amounts of time.
def ye_function(inputs, tools):
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
    # This is our data. Could be URLs to visit.
    input_list = multiprocessing.Queue()
    for i in range(0, 20):
        input_list.put("project " + str(i))

    # These are tools that process the data. Could be webdrivers.
    tool_list = multiprocessing.Queue()
    for j in ["A", "B", "C", "D", "E"]:
        tool_list.put("tool " + str(j))

    # Spin up several processes, but not more than we have tools.
    # Leave some CPU for other people.
    num_processes = min(len(tool_list), multiprocessing.cpu_count() - 1)
    processes = []

    for n in range(0, num_processes):
        # Creating processes that will run in parallel.
        p = multiprocessing.Process(
            target=ye_function,
            args=(
                input_list,
                tool_list,
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
