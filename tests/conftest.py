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

"""Pytest configuration."""

from __future__ import absolute_import, print_function

import json
import os
import shutil
import tempfile
from functools import partial

import httpretty
import pytest
from flask import Flask, current_app, url_for
from flask_babelex import Babel
from flask_breadcrumbs import Breadcrumbs
from flask_celeryext import FlaskCeleryExt
from flask_cli import FlaskCLI
from flask_mail import Mail
from flask_menu import Menu
from invenio_accounts import InvenioAccounts
from invenio_accounts.views import blueprint as accounts_blueprint
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
from invenio_pidstore import InvenioPIDStore
from invenio_records import InvenioRecords
from invenio_records_rest import InvenioRecordsREST
from invenio_records_rest.utils import PIDConverter
from invenio_search import InvenioSearch
from invenio_webhooks import InvenioWebhooks
from invenio_webhooks.models import Receiver
from invenio_webhooks.views import blueprint as webhooks_blueprint
from sqlalchemy_utils.functions import create_database, database_exists

from invenio_github import InvenioGitHub
from invenio_github.api import GitHubAPI
from invenio_github.receivers import GitHubReceiver


@pytest.yield_fixture()
def app(request):
    """Flask application fixture."""
    instance_path = tempfile.mkdtemp()
    app = Flask('testapp', instance_path=instance_path)
    app.config.update(
        # HTTPretty doesn't play well with Redis.
        # See gabrielfalcao/HTTPretty#110
        CACHE_TYPE='simple',
        CELERY_ALWAYS_EAGER=True,
        CELERY_CACHE_BACKEND='memory',
        CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
        CELERY_RESULT_BACKEND='cache',
        GITHUB_SHIELDSIO_BASE_URL='http://example.org/badge/',
        GITHUB_APP_CREDENTIALS=dict(
            consumer_key='changeme',
            consumer_secret='changeme',
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
        'request_token_params'][
        'scope'] = 'user:email,admin:repo_hook,read:org'
    app.url_map.converters['pid'] = PIDConverter

    FlaskCLI(app)
    celeryext = FlaskCeleryExt(app)
    Babel(app)
    Mail(app)
    Menu(app)
    Breadcrumbs(app)
    InvenioDB(app)
    InvenioAccounts(app)
    app.register_blueprint(accounts_blueprint)
    InvenioOAuthClient(app)
    app.register_blueprint(oauthclient_blueprint)
    InvenioOAuth2Server(app)
    app.register_blueprint(server_blueprint)
    app.register_blueprint(settings_blueprint)
    InvenioPIDStore(app)
    InvenioJSONSchemas(app)
    InvenioRecords(app)
    InvenioSearch(app)
    InvenioIndexer(app)
    InvenioFilesREST(app)
    InvenioRecordsREST(app)
    InvenioDepositREST(app)
    InvenioWebhooks(app)
    celeryext.celery.flask_app = app  # Make sure both apps are the same!
    app.register_blueprint(webhooks_blueprint)
    InvenioGitHub(app)

    with app.app_context():
        yield app

    shutil.rmtree(instance_path)


@pytest.yield_fixture()
def db(app):
    """Database fixture."""
    if not database_exists(str(db_.engine.url)):
        create_database(str(db_.engine.url))
    db_.create_all()
    yield db_
    db_.session.remove()
    db_.drop_all()


@pytest.fixture
def tester_id(app, db):
    """Fixture that contains the test data for models tests."""
    datastore = app.extensions['security'].datastore
    tester = datastore.create_user(
        email='info@invenio-software.org', password='tester',
    )
    db.session.commit()
    return tester.id


@pytest.yield_fixture()
def location(db):
    """File system location."""
    tmppath = tempfile.mkdtemp()

    loc = Location(
        name='testloc',
        uri=tmppath,
        default=True
    )
    db.session.add(loc)
    db.session.commit()

    yield loc

    shutil.rmtree(tmppath)


@pytest.fixture
def deposit_token(app, db, tester_id):
    """Fixture that create an access token."""
    token = Token.create_personal(
        'deposit-personal-{0}'.format(tester_id),
        tester_id,
        scopes=['deposit:write', 'deposit:actions'],
        is_internal=True,
    ).access_token
    db.session.commit()
    return token


@pytest.fixture
def access_token(app, db, tester_id):
    """Fixture that create an access token."""
    token = Token.create_personal(
        'test-personal-{0}'.format(tester_id),
        tester_id,
        scopes=['webhooks:event'],
        is_internal=True,
    ).access_token
    db.session.commit()
    return token


@pytest.fixture
def access_token_no_scope(app, tester_id):
    """Fixture that create an access token without scope."""
    token = Token.create_personal(
        'test-personal-{0}'.format(tester_id),
        tester_id,
        scopes=[''],
        is_internal=True,
    ).access_token
    db.session.commit()
    return token


@pytest.fixture()
def remote_token(app, db, tester_id):
    """Create a remove token for accessing GitHub API."""
    from invenio_oauthclient.models import RemoteToken

    # Create GitHub link
    token = RemoteToken.create(
        tester_id,
        GitHubAPI.remote.consumer_key,
        'test',
        '',
    )
    db.session.commit()
    return token


def tclient_request_factory(client, method, endpoint, urlargs, data,
                            is_json, headers, files, verify_ssl):
    """Make requests with test client package."""
    client_func = getattr(client, method.lower())

    if headers is None:
        headers = [('Content-Type', 'application/json')] if is_json else []

    if data is not None:
        request_args = dict(
            data=json.dumps(data) if is_json else data,
            headers=headers,
        )
    else:
        request_args = {}

    if files is not None:
        data.update({
            'file': (files['file'], data['filename']),
            'name': data['filename']
        })
        del data['filename']

    resp = client_func(
        url_for(
            endpoint,
            _external=True,
            **urlargs
        ),
        # base_url=current_app.config['CFG_SITE_SECURE_URL'],
        **request_args
    )

    # Patch response
    resp.json = lambda: json.loads(resp.data)
    return resp


@pytest.yield_fixture()
def request_factory(app, db, tester_id, remote_token):
    """Prepare GitHub requests."""
    from . import fixtures

    # Init GitHub account and mock up GitHub API
    httpretty.enable()
    fixtures.register_github_api()
    GitHubAPI(user_id=tester_id).init_account()
    httpretty.disable()

    db.session.commit()

    with app.test_request_context():
        client = app.test_client()
        yield partial(tclient_request_factory, client)
