# -*- coding: utf-8 -*-
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


"""Minimal Flask application example for development.

Setup Theme
-----------

.. code-block:: console

   $ npm install -g node-sass clean-css requirejs uglify-js
   $ cd examples
   $ flask -a app.py npm
   $ cd static && npm install && cd ..
   $ flask -a app.py collect
   $ flask -a app.py assets build

Prepare Data
------------

Make sure that ``elasticsearch`` server is running:

.. code-block:: console

   $ elasticsearch

   ... version[2.0.0] ...

Create demo records

.. code-block:: console

   $ flask -a app.py db init
   $ flask -a app.py db create
   $ flask -a app.py index init
   $ flask -a app.py users create info@inveniosoftware.org --password 123456 -a

Configure GitHub Integration
----------------------------

Next you need to obtain client ID and secret for your application from
GitHub: https://github.com/settings/applications/new and export them
as ``GITHUB_KEY`` and ``GITHUB_SECRET``.

If your example app running on your private machine you can use Ultrahook
service to make it "public".

.. code-block:: console

    $ ultrahook github 5000/receivers/github/events/
    Authenticated as <ULTRAHOOK_NAME>
    ...

Export ``ULTRAHOOK_NAME`` as shell variable (``export ULTRAHOOK_NAME=me``).

Run server
----------

Last but not least we start our test server:

.. code-block:: console

   $ flask -a app.py --debug run

"""

from __future__ import absolute_import, print_function

import json
import os
import shutil
import tempfile
from functools import partial

from flask import Flask, current_app, url_for
from flask_babelex import Babel
from flask_celeryext import FlaskCeleryExt
from flask_cli import FlaskCLI
from flask_mail import Mail
from invenio_access import InvenioAccess
from invenio_accounts import InvenioAccounts
from invenio_accounts.views import blueprint as accounts_blueprint
from invenio_assets import InvenioAssets
from invenio_db import db as db_
from invenio_db import InvenioDB
from invenio_deposit import InvenioDepositREST
from invenio_files_rest import InvenioFilesREST
from invenio_files_rest.models import Location
from invenio_indexer import InvenioIndexer
from invenio_jsonschemas import InvenioJSONSchemas
from invenio_oauth2server import InvenioOAuth2Server
from invenio_oauth2server.models import Token
from invenio_oauth2server.views import server_blueprint, settings_blueprint
from invenio_oauthclient import InvenioOAuthClient
from invenio_oauthclient.contrib.github import REMOTE_APP
from invenio_oauthclient.views.client import blueprint as oauthclient_blueprint
from invenio_oauthclient.views.settings import \
    blueprint as oauthclient_settings_blueprint
from invenio_pidstore import InvenioPIDStore
from invenio_records import InvenioRecords
from invenio_records_rest import InvenioRecordsREST
from invenio_records_rest.utils import PIDConverter
from invenio_search import InvenioSearch
from invenio_search_ui import InvenioSearchUI
from invenio_theme import InvenioTheme
from invenio_webhooks import InvenioWebhooks
from invenio_webhooks.models import Receiver
from invenio_webhooks.views import blueprint as webhooks_blueprint
from sqlalchemy_utils.functions import create_database, database_exists

from invenio_github import InvenioGitHub
from invenio_github.api import GitHubAPI
from invenio_github.receivers import GitHubReceiver
from invenio_github.views import github

app = Flask('exampleapp')
app.config.update(
    CELERY_ALWAYS_EAGER=True,
    CELERY_CACHE_BACKEND='memory',
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    CELERY_RESULT_BACKEND='cache',
    GITHUB_INSECURE_SSL=True,
    GITHUB_SHIELDSIO_BASE_URL='http://example.org/badge/',
    GITHUB_APP_CREDENTIALS=dict(
        consumer_key=os.getenv('GITHUB_KEY', 'changeme'),
        consumer_secret=os.getenv('GITHUB_SECRET', 'changeme'),
    ),
    LOGIN_DISABLED=False,
    OAUTHLIB_INSECURE_TRANSPORT=True,
    OAUTH2_CACHE_TYPE='simple',
    OAUTHCLIENT_REMOTE_APPS=dict(
        github=REMOTE_APP,
    ),
    SECRET_KEY='test_key',
    SQLALCHEMY_TRACK_MODIFICATIONS=True,
    SQLALCHEMY_DATABASE_URI=os.getenv('SQLALCHEMY_DATABASE_URI',
                                      'sqlite:///test.db'),
    SECURITY_PASSWORD_HASH='plaintext',
    SECURITY_PASSWORD_SCHEMES=['plaintext'],
    SECURITY_DEPRECATED_PASSWORD_SCHEMES=[],
    TESTING=True,
    WTF_CSRF_ENABLED=False,
)

app.config['OAUTHCLIENT_REMOTE_APPS']['github']['params'][
    'request_token_params']['scope'] = 'user:email,admin:repo_hook,read:org'

ULTRAHOOK_NAME = os.getenv('ULTRAHOOK_NAME')
if ULTRAHOOK_NAME:
    app.config['WEBHOOKS_DEBUG_RECEIVER_URLS'] = dict(
        github='http://github.{name}.ultrahook.com/?'
               'access_token=%(token)s'.format(name=ULTRAHOOK_NAME),
    )

app.url_map.converters['pid'] = PIDConverter

FlaskCLI(app)
celeryext = FlaskCeleryExt(app)
Babel(app)
Mail(app)
InvenioDB(app)
InvenioAssets(app)
InvenioTheme(app)
InvenioAccounts(app)
app.register_blueprint(accounts_blueprint)
InvenioOAuthClient(app)
app.register_blueprint(oauthclient_blueprint)
app.register_blueprint(oauthclient_settings_blueprint)
InvenioOAuth2Server(app)
app.register_blueprint(server_blueprint)
app.register_blueprint(settings_blueprint)
InvenioAccess(app)
InvenioPIDStore(app)
InvenioJSONSchemas(app)
InvenioRecords(app)
InvenioSearch(app)
InvenioSearchUI(app)
InvenioIndexer(app)
InvenioFilesREST(app)
InvenioRecordsREST(app)
InvenioDepositREST(app)
InvenioWebhooks(app)
celeryext.celery.flask_app = app  # Make sure both apps are the same!
app.register_blueprint(webhooks_blueprint)

InvenioGitHub(app)
app.register_blueprint(github.blueprint)
