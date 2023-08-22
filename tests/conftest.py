# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2023 CERN.
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

from collections import namedtuple

import github3
import pytest
from invenio_app.factory import create_api
from invenio_oauthclient.contrib.github import REMOTE_APP as GITHUB_REMOTE_APP
from invenio_oauthclient.contrib.github import REMOTE_REST_APP as GITHUB_REMOTE_REST_APP
from invenio_oauthclient.models import RemoteToken
from invenio_oauthclient.proxies import current_oauthclient
from mock import MagicMock, patch

from .fixtures import (
    ZIPBALL,
    TestGithubRelease,
    github_file_contents,
    github_repo_metadata,
    github_user_metadata,
)


@pytest.fixture(scope="module")
def app_config(app_config):
    """Test app config."""
    app_config.update(
        # HTTPretty doesn't play well with Redis.
        # See gabrielfalcao/HTTPretty#110
        APP_THEME=[],
        CACHE_TYPE="simple",
        CELERY_ALWAYS_EAGER=True,
        CELERY_CACHE_BACKEND="memory",
        CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
        CELERY_RESULT_BACKEND="cache",
        GITHUB_APP_CREDENTIALS=dict(
            consumer_key="changeme",
            consumer_secret="changeme",
        ),
        GITHUB_SHARED_SECRET="changeme",
        GITHUB_INSECURE_SSL=False,
        GITHUB_INTEGRATION_ENABLED=True,
        GITHUB_METADATA_FILE=".invenio.json",
        GITHUB_WEBHOOK_RECEIVER_URL="http://localhost:5000/api/receivers/github/events/?access_token={token}",
        GITHUB_WEBHOOK_RECEIVER_ID="github",
        GITHUB_RELEASE_CLASS=TestGithubRelease,
        LOGIN_DISABLED=False,
        OAUTHLIB_INSECURE_TRANSPORT=True,
        OAUTH2_CACHE_TYPE="simple",
        OAUTHCLIENT_REMOTE_APPS=dict(
            github=GITHUB_REMOTE_APP,
        ),
        OAUTHCLIENT_REST_REMOTE_APPS=dict(
            github=GITHUB_REMOTE_REST_APP,
        ),
        SECRET_KEY="test_key",
        SERVER_NAME="testserver.localdomain",
        SECURITY_PASSWORD_HASH="plaintext",
        SECURITY_PASSWORD_SCHEMES=["plaintext"],
        SECURITY_DEPRECATED_PASSWORD_SCHEMES=[],
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        JSONSCHEMAS_HOST="not-used",
        RECORDS_REFRESOLVER_CLS="invenio_records.resolver.InvenioRefResolver",
        RECORDS_REFRESOLVER_STORE="invenio_jsonschemas.proxies.current_refresolver_store",
        # Storage classes
        FILES_REST_STORAGE_CLASS_LIST=dict(
            L="Local",
            F="Fetch",
            R="Remote",
        ),
        FILES_REST_DEFAULT_STORAGE_CLASS="L",
    )
    app_config["OAUTHCLIENT_REMOTE_APPS"]["github"]["params"]["request_token_params"][
        "scope"
    ] = "user:email,admin:repo_hook,read:org"
    return app_config


@pytest.fixture(scope="module")
def create_app(instance_path):
    """Application factory fixture."""
    return create_api


RunningApp = namedtuple(
    "RunningApp",
    [
        "app",
        "location",
        "cache",
    ],
)


@pytest.fixture()
def running_app(app, location, cache):
    """This fixture provides an app with the typically needed db data loaded.

    All of these fixtures are often needed together, so collecting them
    under a semantic umbrella makes sense.
    """
    return RunningApp(app, location, cache)


@pytest.fixture()
def test_user(app, db, github_remote_app):
    """Creates a test user.

    Links the user to a github RemoteToken.
    """
    datastore = app.extensions["security"].datastore
    user = datastore.create_user(
        email="info@inveniosoftware.org",
        password="tester",
    )

    # Create GitHub link for user
    token = RemoteToken.get(user.id, github_remote_app.consumer_key)
    if not token:
        RemoteToken.create(
            user.id,
            github_remote_app.consumer_key,
            "test",
            "",
        )
    db.session.commit()
    return user


@pytest.fixture()
def github_remote_app():
    """Returns github remote app."""
    return current_oauthclient.oauth.remote_apps["github"]


@pytest.fixture()
def remote_token(test_user, github_remote_app):
    """Returns github RemoteToken for user."""
    token = RemoteToken.get(
        test_user.id,
        github_remote_app.consumer_key,
    )
    return token


@pytest.fixture
def unlinked_user(app, db):
    """Creates an user that is not linked to a remote account."""
    datastore = app.extensions["security"].datastore
    user = datastore.create_user(
        email="unlinked@inveniosoftware.org",
        password="unlinked",
    )
    db.session.commit()
    return user


@pytest.fixture()
def tester_id(test_user):
    """Returns tester id."""
    return test_user.id


@pytest.fixture()
def test_repo_data_one():
    """Test repository."""
    return {"name": "repo-1", "id": 1}


@pytest.fixture()
def test_repo_data_two():
    """Test repository."""
    return {"name": "repo-2", "id": 2}


@pytest.fixture()
def test_repo_data_three():
    """Test repository."""
    return {"name": "arepo", "id": 3}


@pytest.fixture()
def github_api(
    running_app,
    db,
    test_repo_data_one,
    test_repo_data_two,
    test_repo_data_three,
    test_user,
):
    """Github API mock."""
    mock_api = MagicMock()
    mock_api.session = MagicMock()
    mock_api.me.return_value = github3.users.User(
        github_user_metadata(login="auser", email="auser@inveniosoftware.org"),
        mock_api.session,
    )

    repo_1 = github3.repos.Repository(
        github_repo_metadata(
            "auser", test_repo_data_one["name"], test_repo_data_one["id"]
        ),
        mock_api.session,
    )
    repo_1.hooks = MagicMock(return_value=[])
    repo_1.file_contents = MagicMock(return_value=None)
    # # Mock hook creation to retun the hook id '12345'
    hook_instance = MagicMock()
    hook_instance.id = 12345
    repo_1.create_hook = MagicMock(return_value=hook_instance)

    repo_2 = github3.repos.Repository(
        github_repo_metadata(
            "auser", test_repo_data_two["name"], test_repo_data_two["id"]
        ),
        mock_api.session,
    )

    repo_2.hooks = MagicMock(return_value=[])
    repo_2.create_hook = MagicMock(return_value=hook_instance)

    file_path = "test.py"

    def mock_file_content():
        # File contents mocking
        owner = "auser"
        repo = test_repo_data_two["name"]
        ref = ""

        # Dummy data to be encoded as the file contents
        data = "dummy".encode("ascii")
        return github_file_contents(owner, repo, file_path, ref, data)

    file_data = mock_file_content()

    def mock_file_contents(path, ref=None):
        if path == file_path:
            # Mock github3.contents.Content with file_data
            return MagicMock(decoded=file_data)
        return None

    repo_2.file_contents = MagicMock(side_effect=mock_file_contents)

    repo_3 = github3.repos.Repository(
        github_repo_metadata(
            "auser", test_repo_data_three["name"], test_repo_data_three["id"]
        ),
        mock_api.session,
    )
    repo_3.hooks = MagicMock(return_value=[])
    repo_3.file_contents = MagicMock(return_value=None)

    repos = {1: repo_1, 2: repo_2, 3: repo_3}
    repos_by_name = {r.full_name: r for r in repos.values()}
    mock_api.repositories.return_value = repos.values()

    def mock_repo_with_id(id):
        return repos.get(id)

    def mock_repo_by_name(owner, name):
        return repos_by_name.get("/".join((owner, name)))

    mock_api.repository_with_id.side_effect = mock_repo_with_id
    mock_api.repository.side_effect = mock_repo_by_name
    mock_api.markdown.side_effect = lambda x: x
    mock_api.session.head.return_value = MagicMock(status_code=200)
    mock_api.session.get.return_value = MagicMock(raw=ZIPBALL())

    with patch("invenio_github.api.GitHubAPI.api", new=mock_api):
        with patch("invenio_github.api.GitHubAPI._sync_hooks"):
            yield mock_api
