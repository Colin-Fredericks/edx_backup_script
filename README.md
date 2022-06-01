# edx_backup_script

This package pulls course exports from multiple edX courses in a row, using Selenium and a headless Chrome browser.

Using this script requires a plaintext file with the URLs of all the course Export pages you'd like to access, one per line.

Because course exports can range in size from a few MB to a few hundred, you should make sure you have plenty of disk space available before running this script on a large number of courses.

## Chrome Web Driver

This repo includes a Mac version of the [Chrome webdriver](https://chromedriver.chromium.org/), which is licensed under the a [separate set of terms](https://chromium.googlesource.com/chromium/src/+/HEAD/LICENSE). If you need a different version of the driver you'll have to replace that file (using the same name).

Since chromedriver is not a signed Mac application it will throw a warning the first time you run it. Go to System Preferences --> Security and Privacy and tell it to open anyway. You should be able to run it just fine on the next attempt.

## Instructions

To install and use for the first time:

    # clone this repo
    $> git clone https://github.com/Colin-Fredericks/edx_backup_script.git

    # create a virtualenv and activate it
    $> python3 -m venv edxbackup
    $> source edxbackup/bin/activate
    (edxbackup) $>

    # install requirements
    (edxbackup) $> cd edx_backup_script
    (edxbackup) $> pip3 install -r requirements.txt

    # install edx_backup_script
    (edxbackup) $> pip3 install .

    # to add or remove staff
    (edxbackup) $> edx_backup_script /path/to/input/file.txt

    # when done
    (edxbackup) $> deactivate

On later runs you can do a simpler version:

  $> source edxstaff/bin/activate
  (edxstaff) $> edx_backup_script /path/to/input/file.txt
  (edxstaff) $> deactivate

Run the whole process from the top if you need to reinstall (for instance, if the script and/or its requirements change).

## Command-line options:

* -h or --help: print the instructions and quit.
* -v or --visible: run with a visible browser instead of a headless one.
* -o or --output: choose a download folder.
