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
from datetime import datetime, timedelta
from functools import partial

import httpretty
import pytest
from elasticsearch.exceptions import RequestError
from flask import Flask, current_app, url_for
from flask_babelex import Babel
from flask_breadcrumbs import Breadcrumbs
from flask_celeryext import FlaskCeleryExt
from flask_cli import FlaskCLI
from flask_mail import Mail
from flask_menu import Menu
from invenio_accounts import InvenioAccounts
from invenio_accounts.views import blueprint as accounts_blueprint
from invenio_assets import InvenioAssets
from invenio_db import db as db_
from invenio_db import InvenioDB
from invenio_deposit import InvenioDepositREST
from invenio_files_rest import InvenioFilesREST
from invenio_files_rest.models import Location
from invenio_formatter import InvenioFormatter
from invenio_formatter.views import create_badge_blueprint
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
from invenio_records.api import Record
from invenio_records_rest import InvenioRecordsREST
from invenio_records_rest.utils import PIDConverter
from invenio_search import InvenioSearch, current_search, current_search_client
from invenio_webhooks import InvenioWebhooks
from invenio_webhooks.models import Receiver
from invenio_webhooks.views import blueprint as webhooks_blueprint
from mock import MagicMock, patch
from six import b
from sqlalchemy_utils.functions import create_database, database_exists

from invenio_github import InvenioGitHub
from invenio_github.api import GitHubAPI
from invenio_github.models import Release, ReleaseStatus, Repository
from invenio_github.receivers import GitHubReceiver
from invenio_github.views.badge import blueprint as github_badge_blueprint
from invenio_github.views.github import blueprint as github_blueprint


@pytest.yield_fixture()
def app(request):
    """Flask application fixture."""
    instance_path = tempfile.mkdtemp()
    app_ = Flask('testapp', instance_path=instance_path)
    app_.config.update(
        # HTTPretty doesn't play well with Redis.
        # See gabrielfalcao/HTTPretty#110
        CACHE_TYPE='simple',
        CELERY_ALWAYS_EAGER=True,
        CELERY_CACHE_BACKEND='memory',
        CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
        CELERY_RESULT_BACKEND='cache',
        GITHUB_APP_CREDENTIALS=dict(
            consumer_key='changeme',
            consumer_secret='changeme',
        ),
        GITHUB_PID_FETCHER='doi_fetcher',
        LOGIN_DISABLED=False,
        OAUTHLIB_INSECURE_TRANSPORT=True,
        OAUTH2_CACHE_TYPE='simple',
        OAUTHCLIENT_REMOTE_APPS=dict(
            github=REMOTE_APP,
        ),
        SECRET_KEY='test_key',
        SERVER_NAME='testserver',
        SQLALCHEMY_TRACK_MODIFICATIONS=True,
        SQLALCHEMY_DATABASE_URI=os.getenv('SQLALCHEMY_DATABASE_URI',
                                          'sqlite:///test.db'),
        SECURITY_PASSWORD_HASH='plaintext',
        SECURITY_PASSWORD_SCHEMES=['plaintext'],
        SECURITY_DEPRECATED_PASSWORD_SCHEMES=[],
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )
    app_.config['OAUTHCLIENT_REMOTE_APPS']['github']['params'][
        'request_token_params'][
        'scope'] = 'user:email,admin:repo_hook,read:org'
    app_.url_map.converters['pid'] = PIDConverter

    FlaskCLI(app_)
    celeryext = FlaskCeleryExt(app_)
    Babel(app_)
    Mail(app_)
    Menu(app_)
    Breadcrumbs(app_)
    InvenioAssets(app_)
    InvenioDB(app_)
    InvenioAccounts(app_)
    app_.register_blueprint(accounts_blueprint)
    InvenioOAuthClient(app_)
    app_.register_blueprint(oauthclient_blueprint)
    InvenioOAuth2Server(app_)
    app_.register_blueprint(server_blueprint)
    app_.register_blueprint(settings_blueprint)
    InvenioFormatter(app_)

    from .helpers import doi_fetcher
    pidstore = InvenioPIDStore(app_)
    pidstore.register_fetcher('doi_fetcher', doi_fetcher)

    InvenioJSONSchemas(app_)
    InvenioRecords(app_)
    InvenioSearch(app_)
    InvenioIndexer(app_)
    InvenioFilesREST(app_)
    InvenioRecordsREST(app_)
    InvenioDepositREST(app_)
    InvenioWebhooks(app_)
    celeryext.celery.flask_app = app_  # Make sure both apps are the same!
    app_.register_blueprint(webhooks_blueprint)
    InvenioGitHub(app_)
    app_.register_blueprint(github_blueprint)
    app_.register_blueprint(github_badge_blueprint)

    with app_.app_context():
        yield app_

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
        email='info@inveniosoftware.org', password='tester',
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


@pytest.fixture()
def minimal_record(app, db, tester_id):
    """Minimal record metadata that is compliant with the JSON schema."""
    metadata = {
        'doi': 'test/1',
        'recid': 1,
        'resource_type': {'type': 'software'},
        'publication_date': datetime.utcnow().date().isoformat(),
        'title': 'Test title',
        'creators': [
            dict(name='Doe, John', affiliation='Atlantis'),
            dict(name='Smith, Jane', affiliation='Atlantis')
        ],
        'description': 'Test description',
        'access_right': 'open',
    }
    record = Record.create(metadata)
    return record


@pytest.fixture()
def repository_model(app, db, tester_id):
    """Github repository fixture."""
    repository = Repository(
        github_id=1, name='testuser/testrepo', user_id=tester_id)
    db.session.add(repository)
    db.session.commit()
    return repository


@pytest.fixture()
def release_model(app, db, repository_model, minimal_record):
    """Github release fixture."""
    release = Release(
        release_id=1,
        tag='v1.0',
        repository=repository_model,
        status=ReleaseStatus.PUBLISHED,
        recordmetadata=minimal_record.model
    )
    db.session.add(release)
    db.session.commit()
    return release


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
def github_api(app, db, tester_id, remote_token):
    """Github API mock."""
    import github3
    from . import fixtures

    mock_api = MagicMock()
    mock_api.me.return_value = github3.users.User(
        fixtures.USER(login='auser', email='auser@inveniosoftware.org'))

    repo_1 = github3.repos.Repository(fixtures.REPO('auser', 'repo-1', 1))
    repo_1.hooks = MagicMock(return_value=[])
    repo_1.file_contents = MagicMock(return_value=None)

    repo_2 = github3.repos.Repository(fixtures.REPO('auser', 'repo-2', 2))
    repo_2.hooks = MagicMock(return_value=[])

    def mock_metadata_contents(path, ref):
        data = json.dumps(dict(
            upload_type='dataset',
            license='mit-license',
            creators=[
                dict(name='Smith, Joe', affiliation='CERN'),
                dict(name='Smith, Sam', affiliation='NASA'),
            ]
        ))
        return MagicMock(decoded=b(data))
    repo_2.file_contents = MagicMock(side_effect=mock_metadata_contents)

    repo_3 = github3.repos.Repository(fixtures.REPO('auser', 'arepo', 3))
    repo_3.hooks = MagicMock(return_value=[])
    repo_3.file_contents = MagicMock(return_value=None)

    repos = {1: repo_1, 2: repo_2, 3: repo_3}
    repos_by_name = {r.full_name: r for r in repos.values()}
    mock_api.repositories.return_value = repos.values()

    def mock_repo_with_id(id):
        return repos.get(id)

    def mock_repo_by_name(owner, name):
        return repos_by_name.get('/'.join((owner, name)))

    mock_api.repository_with_id.side_effect = mock_repo_with_id
    mock_api.repository.side_effect = mock_repo_by_name
    mock_api.markdown.side_effect = lambda x: x
    mock_api.session.head.return_value = MagicMock(status_code=302)
    mock_api.session.get.return_value = MagicMock(raw=fixtures.ZIPBALL())

    with patch('invenio_github.api.GitHubAPI.api', new=mock_api):
        with patch('invenio_github.api.GitHubAPI._sync_hooks'):
            gh = GitHubAPI(user_id=tester_id)
            with db.session.begin_nested():
                gh.init_account()
            db.session.expire(remote_token.remote_account)
            yield mock_api
