# -*- coding: utf-8 -*-
#
# Copyright (C) 2023-2025 CERN.
#
# Invenio-VCS is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
"""Pytest configuration."""

from __future__ import absolute_import, print_function

from collections import namedtuple
from typing import Any

import pytest
from invenio_app.factory import create_api
from invenio_oauthclient.models import RemoteToken
from invenio_oauthclient.proxies import current_oauthclient

from invenio_vcs.contrib.github import GitHubProviderFactory
from invenio_vcs.contrib.gitlab import GitLabProviderFactory
from invenio_vcs.generic_models import (
    GenericContributor,
    GenericOwner,
    GenericOwnerType,
    GenericRelease,
    GenericRepository,
    GenericUser,
    GenericWebhook,
)
from invenio_vcs.providers import RepositoryServiceProvider
from invenio_vcs.service import VCSService
from invenio_vcs.utils import utcnow
from tests.contrib_fixtures.github import GitHubPatcher
from tests.contrib_fixtures.gitlab import GitLabPatcher
from tests.contrib_fixtures.patcher import TestProviderPatcher

from .fixtures import (
    TestVCSRelease,
)


@pytest.fixture(scope="module")
def app_config(app_config):
    """Test app config."""
    vcs_github = GitHubProviderFactory(
        base_url="https://github.com",
        webhook_receiver_url="http://localhost:5000/api/receivers/github/events/?access_token={token}",
    )
    vcs_gitlab = GitLabProviderFactory(
        base_url="https://gitlab.com",
        webhook_receiver_url="http://localhost:5000/api/receivers/gitlab/events/?access_token={token}",
    )

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
        GITLAB_APP_CREDENTIALS=dict(
            consumer_key="changeme",
            consumer_secret="changeme",
        ),
        VCS_RELEASE_CLASS=TestVCSRelease,
        VCS_PROVIDERS=[vcs_github, vcs_gitlab],
        # TODO: delete this to avoid duplication
        VCS_INTEGRATION_ENABLED=True,
        LOGIN_DISABLED=False,
        OAUTHLIB_INSECURE_TRANSPORT=True,
        OAUTH2_CACHE_TYPE="simple",
        OAUTHCLIENT_REMOTE_APPS=dict(
            github=vcs_github.remote_config,
            gitlab=vcs_gitlab.remote_config,
        ),
        OAUTHCLIENT_REST_REMOTE_APPS=dict(
            github=vcs_github.remote_config,
            gitlab=vcs_gitlab.remote_config,
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
        THEME_FRONTPAGE=False,
    )
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
def test_user(app, db, remote_apps):
    """Creates a test user.

    Links the user to a VCS RemoteToken.
    """
    datastore = app.extensions["security"].datastore
    user = datastore.create_user(
        email="info@inveniosoftware.org",
        password="tester",
    )

    # Create provider links for user
    for app in remote_apps:
        token = RemoteToken.get(user.id, app.consumer_key)
        if not token:
            # This auto-creates the missing RemoteAccount
            RemoteToken.create(
                user.id,
                app.consumer_key,
                "test",
                "",
            )

    db.session.commit()
    return user


@pytest.fixture()
def remote_apps():
    """An example list of configured OAuth apps."""
    return [
        current_oauthclient.oauth.remote_apps["github"],
        current_oauthclient.oauth.remote_apps["gitlab"],
    ]


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
def test_generic_repositories():
    """Provider-common dataset of test repositories."""
    return [
        GenericRepository(
            id="1",
            full_name="repo-1",
            default_branch="main",
            description="Lorem ipsum",
            license_spdx="MIT",
        ),
        GenericRepository(
            id="2",
            full_name="repo-2",
            default_branch="main",
            description="Lorem ipsum",
            license_spdx="MIT",
        ),
        GenericRepository(
            id="3",
            full_name="repo-3",
            default_branch="main",
            description="Lorem ipsum",
            license_spdx="MIT",
        ),
    ]


@pytest.fixture()
def test_generic_contributors():
    """Provider-common dataset of test contributors (same for all repos)."""
    return [
        GenericContributor(
            id="1", username="user1", company="Lorem", display_name="Lorem"
        ),
        GenericContributor(
            id="2", username="user2", contributions_count=10, display_name="Lorem"
        ),
    ]


@pytest.fixture()
def test_collaborators():
    """Provider-common dataset of test collaborators (same for all repos).

    We don't have a built-in generic type for this so we'll use a dictionary.
    """
    return [
        {"id": "1", "username": "user1", "admin": True},
        {"id": "2", "username": "user2", "admin": False},
    ]


@pytest.fixture()
def test_generic_webhooks():
    """Provider-common dataset of test webhooks (same for all repos)."""
    return [
        GenericWebhook(id="1", repository_id="1", url="https://example.com"),
        GenericWebhook(id="2", repository_id="2", url="https://example.com"),
    ]


@pytest.fixture()
def test_generic_user():
    """Provider-common user to own the repositories."""
    return GenericUser(id="1", username="user1", display_name="Test User")


@pytest.fixture()
def test_generic_owner(test_generic_user: GenericUser):
    """GenericOwner representation of the test generic user."""
    return GenericOwner(
        test_generic_user.id,
        test_generic_user.username,
        GenericOwnerType.Person,
        display_name=test_generic_user.display_name,
    )


@pytest.fixture()
def test_generic_release():
    """Provider-common example release."""
    return GenericRelease(
        id="1",
        tag_name="v1.0",
        created_at=utcnow(),
        name="Example release",
        body="Lorem ipsum dolor sit amet",
        published_at=utcnow(),
        tarball_url="https://example.com/v1.0.tar",
        zipball_url="https://example.com/v1.0.zip",
    )


@pytest.fixture()
def test_file():
    """Provider-common example file within a repository (no generic interface available for this)."""
    return {"path": "test.py", "content": "test"}


_provider_patchers: list[type[TestProviderPatcher]] = [GitHubPatcher, GitLabPatcher]


def provider_id(p: type[TestProviderPatcher]):
    """Extract the provider ID to use as the test case ID."""
    return p.provider_factory().id


@pytest.fixture(params=_provider_patchers, ids=provider_id)
def vcs_provider(
    request: pytest.FixtureRequest,
    test_user,
    test_generic_repositories: list[GenericRepository],
    test_generic_contributors: list[GenericContributor],
    test_collaborators: list[dict[str, Any]],
    test_generic_webhooks: list[GenericWebhook],
    test_generic_user: GenericUser,
    test_file: dict[str, Any],
):
    """Call the patcher for the provider and run the test case 'inside' its patch context."""
    patcher_class: type[TestProviderPatcher] = request.param
    patcher = patcher_class(test_user)
    # The patch call returns a generator that yields the provider within the patch context.
    # Use yield from to delegate to the patcher's generator, ensuring tests run within the patch context.
    yield from patcher.patch(
        test_generic_repositories,
        test_generic_contributors,
        test_collaborators,
        test_generic_webhooks,
        test_generic_user,
        test_file,
    )


@pytest.fixture()
def vcs_service(vcs_provider: RepositoryServiceProvider):
    """Return an initialised (but not synced) service object for a provider."""
    svc = VCSService(vcs_provider)
    svc.init_account()
    return svc


@pytest.fixture()
def provider_patcher(vcs_provider: RepositoryServiceProvider):
    """Return the raw patcher object corresponding to the current test's provider."""
    for patcher in _provider_patchers:
        if patcher.provider_factory().id == vcs_provider.factory.id:
            return patcher
    raise ValueError(
        f"Patcher corresponding to ID {vcs_provider.factory.id} not found."
    )
