# edx_backup_script

This package pulls course exports from multiple edX courses in a row, using Selenium and a headless Firefox browser.

Using this script requires a CSV with a URL column, holding the URLs of all the course pages you'd like to access, one per line. They look like this: https://course-authoring.edx.org/course/course-v1:Institution+CourseName+RunNumber

Because course exports can range in size from a few MB to a few hundred, you should make sure you have plenty of disk space available before running this script on a large number of courses.

## Web Driver

This repo includes a Mac version of geckodriver for Firefox, which is under the [Mozilla Public License 2.0](https://github.com/mozilla/geckodriver/blob/master/LICENSE). If you need a different version of the driver you'll have to replace that file (using the same name). It also includes the [Chrome webdriver](https://chromedriver.chromium.org/), which of course has its own [separate set of terms](https://chromium.googlesource.com/chromium/src/+/HEAD/LICENSE). If you have Safari, you already have safaridriver available, though you may have to [enable it](https://developer.apple.com/documentation/webkit/testing_with_webdriver_in_safari).

Since geckodriver is not a signed Mac application it will throw a warning the first time you run it. Go to System Preferences --> Security and Privacy and tell it to open anyway. You should be able to run it just fine on the next attempt.

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

* -h or --help:     Print this message and exit.
* -d or --download: Specify the download directory.
* -c or --chrome:   Use Chrome instead of default Firefox.
* -v or --visible:  Run the browser in normal mode instead of headless.
