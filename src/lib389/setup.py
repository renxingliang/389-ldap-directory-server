#!/usr/bin/env python

# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2015 Red Hat, Inc.
# All rights reserved.
#
# License: GPL (version 3 or any later version).
# See LICENSE for details.
# --- END COPYRIGHT BLOCK ---

#
# A setup.py file
#

from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))

# fedora/rhel versioning or PEP440?; ATM semantic versioning
# with open(path.join(here, 'VERSION'), 'r') as version_file:
# version = version_file.read().strip()

version = "1.4.0.1"

with open(path.join(here, 'README.md'), 'r') as f:
    long_description = f.read()

setup(
    name='lib389',
    license='GPLv3+',
    version=version,
    description='A library for accessing and configuring the 389 Directory ' +
                'Server',
    long_description=long_description,
    url='http://port389.org/wiki/Upstream_test_framework',

    author='Red Hat Inc.',
    author_email='389-devel@lists.fedoraproject.org',

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Testing'],

    keywords='389 directory server test configure',
    packages=find_packages(exclude=['tests*']),

    # find lib389/clitools -name ds\* -exec echo \''{}'\', \;
    data_files=[
        ('/usr/sbin/', [
            # 'lib389/clitools/ds_setup',
            'cli/ds-cockpit-setup',
            'cli/dsctl',
            'cli/dsconf',
            'cli/dscreate',
            'cli/dsidm',
            ]),
    ],

    install_requires=[
        'pyasn1',
        'pyasn1-modules',
        'pytest',
        'python-dateutil',
        'six',
        'enum34;python_version=="2.7"',
        'python-ldap;python_version=="2.7"',
        'pyldap;python_version>="3.4"',
        ],
)
