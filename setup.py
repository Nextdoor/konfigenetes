#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

from setuptools import setup
from setuptools.command.install import install

VERSION = "1.0.0"


class VerifyVersionCommand(install):
    """Custom command to verify that the git tag matches our version"""
    description = "verify that the git tag matches our version"

    def run(self):
        tag = os.getenv("CIRCLE_TAG")

        if tag != VERSION:
            info = "Git tag: {0} does not match the version of this app: {1}".format(tag, VERSION)
            sys.exit(info)


setup(
    name="konfigenetes",
    version=VERSION,
    description="Konfigenetes - Simple Kubernetes Resource Templating",
    long_description=open("README.md").read(),
    url="https://github.com/Nextdoor/konfigenetes",
    author="Nextdoor",
    author_email="eng@nextdoor.com",
    license="Apache License, Version 2",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Apache",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3 :: Only",
    ],
    keywords="kubernetes config configuration template templating build",
    packages=["konfigenetes"],
    install_requires=[
        "PyYAML==3.13",
    ],
    python_requires=">=3",
    cmdclass={
        "verify": VerifyVersionCommand,
    },
    test_suite="konfigenetes.konfigenetes_test"
)
