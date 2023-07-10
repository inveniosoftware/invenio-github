# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2023 CERN.
#
# Invenio is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Invenio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio. If not, see <http://www.gnu.org/licenses/>.
#
# In applying this licence, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as an Intergovernmental Organization
# or submit itself to any jurisdiction.

"""Test GitHub hook."""

import json

# from invenio_rdm_records.proxies import current_rdm_records_service
from invenio_webhooks.models import Event

from invenio_github.api import GitHubAPI
from invenio_github.models import ReleaseStatus, Repository


def test_webhook_post(app, db, tester_id, remote_token, github_api):
    """Test webhook POST success."""
    from . import fixtures

    repo_id = 3
    repo_name = "arepo"
    hook = 1234
    tag = "v1.0"

    repo = Repository.get(github_id=repo_id, name=repo_name)
    if not repo:
        repo = Repository.create(tester_id, repo_id, repo_name)

    api = GitHubAPI(tester_id)

    # Enable repository webhook.
    api.enable_repo(repo, hook)

    payload = json.dumps(fixtures.PAYLOAD("auser", repo_name, repo_id, tag))
    headers = [("Content-Type", "application/json")]
    with app.test_request_context(headers=headers, data=payload):
        event = Event.create(receiver_id="github", user_id=tester_id)
        # Add event to session. Otherwise defaults are not added (e.g. response and response_code)
        db.session.add(event)
        db.session.commit()
        event.process()

    assert event.response_code == 202
    # Validate that a release was created
    assert repo.releases.count() == 1
    release = repo.releases.first()
    assert release.status == ReleaseStatus.PUBLISHED
    assert release.release_id == event.payload["release"]["id"]
    assert release.tag == tag
    # This uuid is a fake one set by TestGithubRelease fixture
    assert str(release.record_id) == "445aaacd-9de1-41ab-af52-25ab6cb93df7"
    assert release.errors is None


def test_webhook_post_fail(app, tester_id, remote_token, github_api):
    """Test webhook POST failure."""
    from . import fixtures

    repo_id = 3
    repo_name = "arepo"
    hook = 1234

    # Create a repository
    repo = Repository.get(github_id=repo_id, name=repo_name)
    if not repo:
        repo = Repository.create(tester_id, repo_id, repo_name)

    api = GitHubAPI(tester_id)

    # Enable repository webhook.
    api.enable_repo(repo, hook)

    # Create an invalid payload (fake repo)
    fake_payload = json.dumps(
        fixtures.PAYLOAD("fake_user", "fake_repo", 1000, "v1000.0")
    )
    headers = [("Content-Type", "application/json")]
    with app.test_request_context(headers=headers, data=fake_payload):
        # user_id = request.oauth.access_token.user_id
        event = Event.create(receiver_id="github", user_id=tester_id)
        event.process()

    # Repo does not exist
    assert event.response_code == 404

    # Create an invalid payload (fake user)
    # TODO 'fake_user' does not match the invenio user 'extra_data'. Should this fail?
    # TODO what should happen if an event is received and the account is not synced?
