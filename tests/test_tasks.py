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

from time import sleep

from invenio_oauthclient.models import RemoteAccount
from invenio_webhooks.models import Event
from mock import patch

from invenio_github.api import GitHubAPI
from invenio_github.models import Release, ReleaseStatus, Repository
from invenio_github.tasks import process_release, refresh_accounts
from invenio_github.utils import iso_utcnow

from . import fixtures


def test_real_process_release_task(
    app, db, location, tester_id, remote_token, github_api
):
    # Initialise account
    api = GitHubAPI(tester_id)
    api.init_account()
    api.sync()

    # Get remote account extra data
    extra_data = remote_token.remote_account.extra_data

    assert 1 in extra_data["repos"]
    assert "repo-1" in extra_data["repos"][1]["full_name"]
    assert 2 in extra_data["repos"]
    assert "repo-2" in extra_data["repos"][2]["full_name"]

    repo_name = "repo-1"
    repo_id = 1

    repo = Repository.create(tester_id, repo_id, repo_name)
    api.enable_repo(repo, 12345)
    event = Event(
        receiver_id="github",
        user_id=tester_id,
        payload=fixtures.PAYLOAD("auser", "repo-1", 1),
    )

    release_object = Release(
        release_id=event.payload["release"]["id"],
        tag=event.payload["release"]["tag_name"],
        repository=repo,
        event=event,
        status=ReleaseStatus.RECEIVED,
    )
    db.session.add(release_object)
    db.session.commit()

    process_release.delay(release_object.release_id)
    assert repo.releases.count() == 1
    release = repo.releases.first()
    assert release.status == ReleaseStatus.PUBLISHED
    # This uuid is a fake one set by TestGithubRelease fixture
    assert str(release.record_id) == "445aaacd-9de1-41ab-af52-25ab6cb93df7"


def test_refresh_accounts(app, db, tester_id, remote_token, github_api):
    """Test account refresh task."""

    def mocked_sync(hooks=True, async_hooks=True):
        """Mock sync function and update the remote account."""
        account = RemoteAccount.query.all()[0]
        account.extra_data.update(
            dict(
                last_sync=iso_utcnow(),
            )
        )
        db.session.commit()

    with patch("invenio_github.api.GitHubAPI.sync", side_effect=mocked_sync):
        updated = RemoteAccount.query.all()[0].updated
        expiration_threshold = {"seconds": 1}
        sleep(2)
        refresh_accounts.delay(expiration_threshold)

        last_update = RemoteAccount.query.all()[0].updated
        assert updated != last_update

        refresh_accounts.delay(expiration_threshold)

        assert last_update == RemoteAccount.query.all()[0].updated
