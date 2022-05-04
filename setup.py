#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
from setuptools import setup
from setuptools import find_packages


project_name = "edx_backup_script"


def get_version(*file_paths):
    """Retrieves the version from [your_package]/__init__.py"""
    filename = os.path.join(os.path.dirname(__file__), *file_paths)
    version_file = open(filename).read()
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


version = get_version(project_name, "__init__.py")


with open("README.md") as readme_file:
    readme = readme_file.read()

requirements = [
    "async-generator",
    "attrs",
    "certifi",
    "cffi",
    "cryptography",
    "h11",
    "idna",
    "outcome",
    "pycparser",
    "pyOpenSSL",
    "PySocks",
    "selenium",
    "sniffio",
    "sortedcontainers",
    "trio",
    "trio-websocket",
    "urllib3",
    "wsproto",
]

test_requirements = [
    # TODO: put package test requirements here
]

setup(
    name=project_name,
    version=version,
    description="Downloads edX course exports from multiple courses",
    long_description=readme,
    author="Colin Fredericks",
    author_email="colin_fredericks@harvard.edu",
    url="https://github.com/Colin_Fredericks/" + project_name,
    packages=find_packages(exclude=["tests*"]),
    entry_points={
        "console_scripts": [
            "{}={}.ReplaceEdXStaff:PullEdXBackups".format(project_name, project_name),
        ]
    },
    data_files=[("webdriver", ["edx_backup_script/chromedriver"])],
    include_package_data=True,
    install_requires=requirements,
    zip_safe=False,
    keywords="hx edx backup tarball " + project_name,
    classifiers=[
        "Development Status :: Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.8",
    ],
    test_suite="tests",
    tests_require=test_requirements,
)
