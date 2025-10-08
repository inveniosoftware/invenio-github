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
from unittest.mock import patch

from invenio_oauthclient.models import RemoteAccount
from invenio_webhooks.models import Event

from invenio_vcs.generic_models import (
    GenericOwner,
    GenericRelease,
    GenericRepository,
)
from invenio_vcs.models import Release, ReleaseStatus
from invenio_vcs.providers import RepositoryServiceProvider
from invenio_vcs.service import VCSService
from invenio_vcs.tasks import process_release, refresh_accounts
from invenio_vcs.utils import iso_utcnow
from tests.contrib_fixtures.patcher import TestProviderPatcher


def test_real_process_release_task(
    db,
    tester_id,
    vcs_service: VCSService,
    test_generic_repositories: list[GenericRepository],
    test_generic_release: GenericRelease,
    test_generic_owner: GenericOwner,
    provider_patcher: TestProviderPatcher,
):
    vcs_service.sync()

    generic_repo = test_generic_repositories[0]
    vcs_service.enable_repository(generic_repo.id)
    db_repo = vcs_service.get_repository(repo_id=generic_repo.id)

    event = Event(
        # Receiver ID is same as provider ID
        receiver_id=vcs_service.provider.factory.id,
        user_id=tester_id,
        payload=provider_patcher.test_webhook_payload(
            generic_repo, test_generic_release, test_generic_owner
        ),
    )

    db_release = Release(
        provider=vcs_service.provider.factory.id,
        provider_id=test_generic_release.id,
        tag=test_generic_release.tag_name,
        repository=db_repo,
        event=event,
        status=ReleaseStatus.RECEIVED,
    )
    db.session.add(db_release)
    db.session.commit()

    process_release.delay(vcs_service.provider.factory.id, db_release.provider_id)
    assert db_repo.releases.count() == 1
    release = db_repo.releases.first()
    assert release.status == ReleaseStatus.PUBLISHED
    # This uuid is a fake one set by TestGithubRelease fixture
    assert str(release.record_id) == "445aaacd-9de1-41ab-af52-25ab6cb93df7"


def test_refresh_accounts(db, test_user, vcs_provider: RepositoryServiceProvider):
    def mocked_sync(hooks=True, async_hooks=True):
        account = RemoteAccount.query.all()[0]
        account.extra_data.update(
            dict(
                last_sync=iso_utcnow(),
            )
        )
        db.session.commit()

    with patch("invenio_vcs.service.VCSService.sync", side_effect=mocked_sync):
        updated = RemoteAccount.query.all()[0].updated
        expiration_threshold = {"seconds": 1}
        sleep(2)
        refresh_accounts.delay(vcs_provider.factory.id, expiration_threshold)

        last_update = RemoteAccount.query.all()[0].updated
        assert updated != last_update

        refresh_accounts.delay(vcs_provider.factory.id, expiration_threshold)

        assert last_update == RemoteAccount.query.all()[0].updated
