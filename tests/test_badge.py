# -*- coding: utf-8 -*-
#
# Copyright (C) 2023-2025 CERN.
#
# Invenio-VCS is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
"""Test cases for badge creation."""

from __future__ import absolute_import

from unittest.mock import patch

import pytest
from flask import url_for
from flask_login import login_user
from invenio_accounts.testutils import login_user_via_session
from invenio_webhooks.models import Event

from invenio_vcs.generic_models import GenericRelease, GenericRepository
from invenio_vcs.models import Release, ReleaseStatus, Repository
from invenio_vcs.service import VCSService


@pytest.mark.skip(reason="Unit tests for UI routes are unimplemented.")
def test_badge_views(
    app,
    db,
    client,
    test_user,
    test_generic_repositories: list[GenericRepository],
    test_generic_release: GenericRelease,
    vcs_service: VCSService,
):
    """Test create_badge method."""
    vcs_service.sync(hooks=False)
    generic_repo = test_generic_repositories[0]
    db_repo = Repository.get(
        provider=vcs_service.provider.factory.id, provider_id=generic_repo.id
    )
    db_repo.enabled_by_user_id = test_user.id
    db.session.add(db_repo)

    event = Event(
        # Receiver ID is same as provider ID
        receiver_id=vcs_service.provider.factory.id,
        user_id=test_user.id,
        payload={},
    )

    db_release = Release(
        provider=vcs_service.provider.factory.id,
        provider_id=test_generic_release.id,
        tag=test_generic_release.tag_name,
        repository=db_repo,
        event=event,
        status=ReleaseStatus.PUBLISHED,
    )
    db.session.add(db_release)
    db.session.commit()

    login_user(test_user)
    login_user_via_session(client, email=test_user.email)

    def mock_url_for(target: str, **kwargs):
        """The badge route handler calls url_for referencing a module we don't have access to during the test run.

        Testing the functionality of that module is out of scope here.
        """
        return "https://example.com"

    with patch("invenio_vcs.views.badge.url_for", mock_url_for):
        badge_url = url_for(
            "invenio_vcs_badge.index",
            provider=vcs_service.provider.factory.id,
            repo_provider_id=generic_repo.id,
        )
        badge_resp = client.get(badge_url)
        # Expect a redirect to the badge formatter
        assert badge_resp.status_code == 302

    class TestAbortException(Exception):
        def __init__(self, code: int) -> None:
            self.code = code

    # Test with non-existent provider id
    with patch(
        "invenio_vcs.views.badge.abort",
        # This would crash with the actual abort function as it would try to render the 404 Jinja
        # template which is not available during tests.
        lambda code: (_ for _ in ()).throw(TestAbortException(code)),
    ):
        badge_url = url_for(
            "invenio_vcs_badge.index",
            provider=vcs_service.provider.factory.id,
            repo_provider_id="42",
        )
        with pytest.raises(TestAbortException) as e:
            client.get(badge_url)

        assert e.value.code == 404
