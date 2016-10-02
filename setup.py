# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016 CERN.
#
# Invenio is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Invenio module that adds GitHub integration to the platform."""

import os

from setuptools import find_packages, setup

readme = open('README.rst').read()
history = open('CHANGES.rst').read()

tests_require = [
    'check-manifest>=0.25',
    'coverage>=4.0',
    'httpretty>=0.8.14',
    'invenio-files-rest>=1.0.0a12',
    'isort>=4.2.2',
    'mock>=2.0.0',
    'pydocstyle>=1.0.0',
    'pytest-cache>=1.0',
    'pytest-cov>=1.8.0',
    'pytest-pep8>=1.0.6',
    'pytest>=2.8.0',
]

extras_require = {
    'docs': [
        'Sphinx>=1.4.2',
    ],
    'tests': tests_require,
}

extras_require['all'] = []
for reqs in extras_require.values():
    extras_require['all'].extend(reqs)

setup_requires = [
    'Babel>=1.3',
    'pytest-runner>=2.6.2',
]

install_requires = [
    'Flask-BabelEx>=0.9.2',
    'Flask-Breadcrumbs>=0.3.0',
    'Flask-Menu>=0.5.0',
    'Flask>=0.11.1',
    'github3.py>=1.0.0a4',
    'humanize>=0.5.1',
    'invenio-assets>=1.0.0a4',
    'invenio-accounts>=1.0.0a15',
    'invenio-celery>=1.0.0a4',
    'invenio-db>=1.0.0b2',
    'invenio-deposit>=1.0.0a2',
    'invenio-formatter[badges]>=1.0.0a2',
    'invenio-oauth2server>=1.0.0a10',
    'invenio-oauthclient>=1.0.0a8',
    'invenio-pidstore>=1.0.0a9',
    'invenio-records>=1.0.0a16',
    'invenio-webhooks>=1.0.0a3',
    'mistune>=0.7.2',
    'six>=1.10.0',
    'uritemplate.py>=0.2.0,<2.0',
]

packages = find_packages()


# Get the version string. Cannot be done with import!
g = {}
with open(os.path.join('invenio_github', 'version.py'), 'rt') as fp:
    exec(fp.read(), g)
    version = g['__version__']

setup(
    name='invenio-github',
    version=version,
    description=__doc__,
    long_description=readme + '\n\n' + history,
    keywords='invenio github',
    license='GPLv2',
    author='CERN',
    author_email='info@inveniosoftware.org',
    url='https://github.com/inveniosoftware/invenio-github',
    packages=packages,
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    entry_points={
        'invenio_base.apps': [
            'invenio_github = invenio_github:InvenioGitHub',
        ],
        'invenio_base.blueprints': [
            'invenio_github_badge = invenio_github.views.badge:blueprint',
            'invenio_github_github = invenio_github.views.github:blueprint',
        ],
        'invenio_celery.tasks': [
            'invenio_github = invenio_github.tasks',
        ],
        'invenio_db.models': [
            'invenio_github = invenio_github.models',
        ],
        'invenio_i18n.translations': [
            'messages = invenio_github',
        ],
        'invenio_webhooks.receivers': [
            'github = invenio_github.receivers:GitHubReceiver',
        ],
        'invenio_admin.views': [
            'invenio_github_repository = '
            'invenio_github.admin:repository_adminview',
            'invenio_github_requests = '
            'invenio_github.admin:release_adminview',
        ],
        'invenio_assets.bundles': [
            'invenio_github_js = invenio_github.bundles:js',
            'invenio_github_css = invenio_github.bundles:css',
        ],
    },
    extras_require=extras_require,
    install_requires=install_requires,
    setup_requires=setup_requires,
    tests_require=tests_require,
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Development Status :: 3 - Alpha',
    ],
)
