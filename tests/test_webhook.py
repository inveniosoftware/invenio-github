# -*- coding: utf-8 -*-
# This file is part of Invenio.
# Copyright (C) 2025 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Test vcs hook."""

import json

# from invenio_rdm_records.proxies import current_rdm_records_service
from invenio_webhooks.models import Event

from invenio_vcs.generic_models import (
    GenericOwner,
    GenericOwnerType,
    GenericRelease,
    GenericRepository,
    GenericWebhook,
)
from invenio_vcs.models import ReleaseStatus, Repository
from invenio_vcs.utils import utcnow
from tests.contrib_fixtures.patcher import TestProviderPatcher


def test_webhook_post(
    app,
    db,
    tester_id,
    test_generic_repositories: list[GenericRepository],
    test_generic_webhooks: list[GenericWebhook],
    test_generic_release: GenericRelease,
    test_generic_owner: GenericOwner,
    provider_patcher: TestProviderPatcher,
):
    generic_repo = test_generic_repositories[0]
    generic_webhook = next(
        h for h in test_generic_webhooks if h.repository_id == generic_repo.id
    )

    db_repo = Repository.get(
        provider=provider_patcher.provider_factory().id, provider_id=generic_repo.id
    )
    if not db_repo:
        db_repo = Repository.create(
            provider=provider_patcher.provider_factory().id,
            provider_id=generic_repo.id,
            default_branch=generic_repo.default_branch,
            full_name=generic_repo.full_name,
            description=generic_repo.description,
            license_spdx=generic_repo.license_spdx,
        )

    # Enable repository webhook.
    db_repo.hook = generic_webhook.id
    db_repo.enabled_by_user_id = tester_id
    db.session.add(db_repo)
    db.session.commit()

    payload = json.dumps(
        provider_patcher.test_webhook_payload(
            generic_repo, test_generic_release, test_generic_owner
        )
    )
    headers = [("Content-Type", "application/json")]
    with app.test_request_context(headers=headers, data=payload):
        event = Event.create(
            receiver_id=provider_patcher.provider_factory().id, user_id=tester_id
        )
        # Add event to session. Otherwise defaults are not added (e.g. response and response_code)
        db.session.add(event)
        db.session.commit()
        event.process()

    assert event.response_code == 202
    # Validate that a release was created
    assert db_repo.releases.count() == 1
    release = db_repo.releases.first()
    assert release.status == ReleaseStatus.PUBLISHED
    assert release.provider_id == test_generic_release.id
    assert release.tag == test_generic_release.tag_name
    # This uuid is a fake one set by TestVCSRelease fixture
    assert str(release.record_id) == "445aaacd-9de1-41ab-af52-25ab6cb93df7"
    assert release.errors is None


def test_webhook_post_fail(
    app,
    tester_id,
    test_generic_repositories: list[GenericRepository],
    test_generic_webhooks: list[GenericWebhook],
    provider_patcher: TestProviderPatcher,
):
    generic_repo = test_generic_repositories[0]
    generic_webhook = next(
        h for h in test_generic_webhooks if h.repository_id == generic_repo.id
    )

    db_repo = Repository.get(
        provider=provider_patcher.provider_factory().id, provider_id=generic_repo.id
    )
    if not db_repo:
        db_repo = Repository.create(
            provider=provider_patcher.provider_factory().id,
            provider_id=generic_repo.id,
            default_branch=generic_repo.default_branch,
            full_name=generic_repo.full_name,
            description=generic_repo.description,
            license_spdx=generic_repo.license_spdx,
        )

    # Enable repository webhook.
    db_repo.hook = generic_webhook.id
    db_repo.enabled_by_user_id = tester_id

    # Create an invalid payload (fake repo)
    fake_payload = json.dumps(
        provider_patcher.test_webhook_payload(
            GenericRepository(
                id="123",
                full_name="fake_repo",
                default_branch="fake_branch",
            ),
            GenericRelease(
                id="123",
                tag_name="v123.345",
                created_at=utcnow(),
            ),
            GenericOwner(id="123", path_name="fake_user", type=GenericOwnerType.Person),
        )
    )
    headers = [("Content-Type", "application/json")]
    with app.test_request_context(headers=headers, data=fake_payload):
        # user_id = request.oauth.access_token.user_id
        event = Event.create(
            receiver_id=provider_patcher.provider_factory().id, user_id=tester_id
        )
        event.process()

    # Repo does not exist
    assert event.response_code == 404
