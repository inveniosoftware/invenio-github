# -*- coding: utf-8 -*-
#
# Copyright (C) 2023-2025 CERN.
#
# Invenio-VCS is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
"""Test invenio-vcs service layer."""

import json

import pytest
from invenio_webhooks.models import Event

from invenio_vcs.generic_models import (
    GenericOwner,
    GenericRelease,
    GenericRepository,
)
from invenio_vcs.models import Release, ReleaseStatus
from invenio_vcs.service import VCSRelease, VCSService
from tests.contrib_fixtures.patcher import TestProviderPatcher


def test_vcs_service_user_repositories(
    vcs_service: VCSService,
    test_generic_repositories: list[GenericRepository],
):
    vcs_service.sync()

    user_available_repositories = list(vcs_service.user_available_repositories)
    assert len(user_available_repositories) == len(test_generic_repositories)

    repo_id = test_generic_repositories[0].id
    assert user_available_repositories[0].provider_id == repo_id

    # We haven't enabled any repositories yet
    user_enabled_repositories = list(vcs_service.user_enabled_repositories)
    assert len(user_enabled_repositories) == 0

    vcs_service.enable_repository(repo_id)
    user_enabled_repositories = list(vcs_service.user_enabled_repositories)
    assert len(user_enabled_repositories) == 1
    assert user_enabled_repositories[0].provider_id == repo_id
    assert user_enabled_repositories[0].hook is not None

    vcs_service.disable_repository(repo_id)
    user_enabled_repositories = list(vcs_service.user_enabled_repositories)
    assert len(user_enabled_repositories) == 0


def test_vcs_service_list_repos(vcs_service: VCSService):
    vcs_service.sync()
    repos = vcs_service.list_repositories()
    assert len(repos) == 3


def test_vcs_service_get_repo_default_branch(
    vcs_service: VCSService, test_generic_repositories: list[GenericRepository]
):
    vcs_service.sync()
    default_branch = vcs_service.get_repo_default_branch(
        test_generic_repositories[0].id
    )
    assert default_branch == test_generic_repositories[0].default_branch


def test_vcs_service_get_last_sync_time(vcs_service: VCSService):
    vcs_service.sync()
    last_sync_time = vcs_service.get_last_sync_time()
    assert last_sync_time is not None


def test_vcs_service_get_repository(
    vcs_service: VCSService, test_generic_repositories: list[GenericRepository]
):
    vcs_service.sync()
    repository = vcs_service.get_repository(test_generic_repositories[0].id)
    assert repository is not None
    assert repository.provider_id == test_generic_repositories[0].id


def test_release_api(
    app,
    test_user,
    test_generic_repositories: list[GenericRepository],
    test_generic_release: GenericRelease,
    test_generic_owner: GenericOwner,
    provider_patcher: TestProviderPatcher,
    vcs_service: VCSService,
):
    repo = test_generic_repositories[0]
    headers = [("Content-Type", "application/json")]

    payload = provider_patcher.test_webhook_payload(
        repo, test_generic_release, test_generic_owner
    )
    with app.test_request_context(headers=headers, data=json.dumps(payload)):
        event = Event.create(
            receiver_id=provider_patcher.provider_factory().id,
            user_id=test_user.id,
        )
        release = Release(
            provider_id=test_generic_release.id,
            tag=test_generic_release.tag_name,
            repository_id=repo.id,
            event=event,
            status=ReleaseStatus.RECEIVED,
        )

        # Idea is to test the public interface of VCSRelease
        r = VCSRelease(release, vcs_service.provider)

        # Validate that public methods raise NotImplementedError
        with pytest.raises(NotImplementedError):
            r.process_release()

        with pytest.raises(NotImplementedError):
            r.publish()

        # Validate that an invalid file returns None
        invalid_remote_file_contents = vcs_service.provider.retrieve_remote_file(
            repo.id, release.tag, "test"
        )

        assert invalid_remote_file_contents is None

        # Validate that a valid file returns its data
        valid_remote_file_contents = vcs_service.provider.retrieve_remote_file(
            repo.id, release.tag, "test.py"
        )

        assert valid_remote_file_contents is not None
        assert isinstance(valid_remote_file_contents, bytes)


"""

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
        rel_api = VCSRelease(release)
        resolved_url = rel_api.resolve_zipball_url()
        ref_tag_url = (
            "https://github.com/auser/repo-2/zipball/refs/tags/v1.0-tag-and-branch"
        )
        assert resolved_url == ref_tag_url
        # Check that the original zipball URL from the event payload is not the same
        assert rel_api.release_zipball_url != ref_tag_url
"""
