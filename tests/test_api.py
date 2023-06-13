# -*- coding: utf-8 -*-
#
# Copyright (C) 2023 CERN.
#
# Invenio-Github is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
"""Test invenio-github api."""
import json

import pytest
from invenio_webhooks.models import Event

from invenio_github.api import GitHubAPI, GitHubRelease
from invenio_github.models import Release, ReleaseStatus

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
