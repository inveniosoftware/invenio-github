# -*- coding: utf-8 -*-
#
# Copyright (C) 2023-2025 CERN.
#
# Invenio-Github is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
"""Test invenio-github api."""

import json
import time
from unittest.mock import patch

import pytest
from invenio_webhooks.models import Event

from invenio_github.api import GitHubAPI, GitHubRelease
from invenio_github.models import Release, ReleaseStatus, Repository

from .fixtures import PAYLOAD as github_payload_fixture

# GithubAPI tests


def test_github_api_create_hook(app, test_user, github_api):
    """Test hook creation."""
    api = GitHubAPI(test_user.id)
    api.init_account()
    repo_id = 1
    repo_name = "repo-1"
    hook_created = api.create_hook(repo_id=repo_id, repo_name=repo_name)
    assert hook_created


# GithubRelease api tests


def test_release_api(app, test_user, github_api):
    api = GitHubAPI(test_user.id)
    api.init_account()
    repo_id = 2
    repo_name = "repo-2"

    # Create a repo hook
    hook_created = api.create_hook(repo_id=repo_id, repo_name=repo_name)
    assert hook_created

    headers = [("Content-Type", "application/json")]

    payload = github_payload_fixture("auser", repo_name, repo_id, tag="v1.0")
    with app.test_request_context(headers=headers, data=json.dumps(payload)):
        event = Event.create(
            receiver_id="github",
            user_id=test_user.id,
        )
        release = Release(
            release_id=payload["release"]["id"],
            tag=event.payload["release"]["tag_name"],
            repository_id=repo_id,
            event=event,
            status=ReleaseStatus.RECEIVED,
        )
        # Idea is to test the public interface of GithubRelease
        gh = GitHubRelease(release)

        # Validate that public methods raise NotImplementedError
        with pytest.raises(NotImplementedError):
            gh.process_release()

        with pytest.raises(NotImplementedError):
            gh.publish()

        assert getattr(gh, "retrieve_remote_file") is not None

        # Validate that an invalid file returns None
        invalid_remote_file_contents = gh.retrieve_remote_file("test")

        assert invalid_remote_file_contents is None

        # Validate that a valid file returns its data
        valid_remote_file_contents = gh.retrieve_remote_file("test.py")

        assert valid_remote_file_contents is not None
        assert valid_remote_file_contents.decoded["name"] == "test.py"


def test_release_branch_tag_conflict(app, test_user, github_api):
    api = GitHubAPI(test_user.id)
    api.init_account()
    repo_id = 2
    repo_name = "repo-2"

    # Create a repo hook
    hook_created = api.create_hook(repo_id=repo_id, repo_name=repo_name)
    assert hook_created

    headers = [("Content-Type", "application/json")]

    payload = github_payload_fixture(
        "auser", repo_name, repo_id, tag="v1.0-tag-and-branch"
    )
    with app.test_request_context(headers=headers, data=json.dumps(payload)):
        event = Event.create(
            receiver_id="github",
            user_id=test_user.id,
        )
        release = Release(
            release_id=payload["release"]["id"],
            tag=event.payload["release"]["tag_name"],
            repository_id=repo_id,
            event=event,
            status=ReleaseStatus.RECEIVED,
        )
        # Idea is to test the public interface of GithubRelease
        rel_api = GitHubRelease(release)
        resolved_url = rel_api.resolve_zipball_url()
        ref_tag_url = (
            "https://github.com/auser/repo-2/zipball/refs/tags/v1.0-tag-and-branch"
        )
        assert resolved_url == ref_tag_url
        # Check that the original zipball URL from the event payload is not the same
        assert rel_api.release_zipball_url != ref_tag_url


def test_sync_basic(app, test_user, github_api):
    """Test basic sync functionality."""
    api = GitHubAPI(test_user.id)
    api.init_account()

    # Test sync without hooks
    api.sync(hooks=False)

    # Verify account extra data is updated
    assert api.account.extra_data["repos"] is not None
    assert api.account.extra_data["last_sync"] is not None


def test_sync_updates_repo_names(app, test_user, github_api, db):
    """Test that sync updates repository names when they change on GitHub."""

    api = GitHubAPI(test_user.id)
    api.init_account()

    # Create a repository with old name
    repo = Repository.create(test_user.id, 1, "old-name/repo")
    db.session.add(repo)
    db.session.commit()

    old_repo = Repository.query.filter_by(github_id=1).first()
    assert old_repo.name == "old-name/repo"

    # Sync (GitHub API mock should return updated name)
    api.sync(hooks=False)

    # Check if repository name was updated
    updated_repo = Repository.query.filter_by(github_id=1).first()
    assert updated_repo.name == "auser/repo-1"


def test_sync_updates_account_extra_data(app, test_user, github_api):
    """Test that sync properly updates account extra data."""
    api = GitHubAPI(test_user.id)
    api.init_account()

    assert "last_sync" in api.account.extra_data
    old_last_sync = api.account.extra_data["last_sync"]

    # Sync
    api.sync(hooks=False)

    # Verify extra data was updated
    assert api.account.extra_data["repos"] is not None
    assert api.account.extra_data["last_sync"] != old_last_sync


def test_sync_updates_hooks_asynchronously(app, test_user, github_api_with_hooks, db):
    """Test that sync properly updates hooks when async_hooks=True."""
    api = GitHubAPI(test_user.id)
    api.init_account()

    num_repos = len(api.api.repositories())

    # patch the GitHubAPI to simulate some delay in hook synchronization
    delay = 0.2
    expected_duration = delay * num_repos
    with patch.object(
        api, "sync_repo_hook", side_effect=lambda *args, **kwargs: time.sleep(delay)
    ):
        # Measure how long the Sync takes with async_hooks=True
        start_time = time.time()
        api.sync(async_hooks=True)
        duration = time.time() - start_time
        assert duration < expected_duration

        # Measure how long the Sync takes with async_hooks=False
        start_time = time.time()
        api.sync(hooks=True, async_hooks=False)
        duration = time.time() - start_time
        # assert that sync_repo_hook was called once for each of the three repos
        # during sync with async_hooks=False
        assert api.sync_repo_hook.call_count == num_repos
        # assert that the duration is at least three times the simulated delay
        assert duration >= expected_duration


def test_sync_repo_hook_creates_repo_when_hook_exists(app, test_user, github_api, db):
    """Test that sync_repo_hook creates a repository when a valid hook exists on GitHub."""
    api = GitHubAPI(test_user.id)
    api.init_account()

    repo_id = 1

    # Sync repo hook - should create repository since hook exists in mocked GitHub
    api.sync_repo_hook(repo_id)

    # Commit changes to ensure repository is persisted
    db.session.commit()

    # Verify repository was created
    repo = Repository.query.filter_by(github_id=repo_id).first()
    assert repo is not None
    assert repo.github_id == repo_id
    assert repo.name == "auser/repo-1"
    assert repo.user_id == test_user.id
    assert repo.hook is not None


def test_sync_repo_hook_enables_existing_repo_when_hook_exists(
    app, test_user, github_api, db
):
    """Test that sync_repo_hook enables an existing disabled repository when hook exists."""
    api = GitHubAPI(test_user.id)
    api.init_account()

    repo_id = 1
    repo_name = "auser/repo-1"

    # Create a disabled repository
    repo = Repository.create(test_user.id, repo_id, repo_name)
    repo.hook = 0
    db.session.add(repo)
    db.session.commit()

    # Sync repo hook
    api.sync_repo_hook(repo_id)

    # Verify repository was enabled
    updated_repo = Repository.query.filter_by(github_id=repo_id).first()
    assert updated_repo.user_id == test_user.id
    assert updated_repo.hook > 0
