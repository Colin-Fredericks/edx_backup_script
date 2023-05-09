#! usr/bin/env python3
# Reads in a list of edX tarballs and renames them
# according to the course name and run number.

import os
import glob
import tarfile
import argparse
import lxml.etree as ET

def rename_tarfile(filename):
    # Read the tarfile without extracting it
    print('Reading: ' + filename)
    tar = tarfile.open(filename, 'r')

    # Get the course name and run number from the course.xml file
    # It looks like this: <course url_name="3T2022" org="HarvardX" course="SW12.6x"/>
    course_xml = tar.extractfile('course/course.xml')
    tree = ET.parse(course_xml)
    root = tree.getroot()
    run_number = root.attrib['url_name']
    course_name = root.attrib['course']

    # Close the tarfile
    tar.close()

    # Rename the tarfile
    new_name = course_name + '_' + run_number + '.tar.gz'
    os.rename(filename, new_name)
    print('Renamed to: ' + new_name)



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filenames', help='A glob pattern for the tarfiles to rename', nargs='+')
    args = parser.parse_args()

    # filenames = glob.glob(args.tarfiles)
    for filename in args.filenames:
        rename_tarfile(filename)

    print('Done!')

if __name__ == "__main__":
    main()