# -*- coding: utf-8 -*-
#
# Copyright (C) 2023 CERN.
#
# Invenio-VCS is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
"""Test invenio-vcs views."""

from flask import url_for
from flask_security import login_user
from invenio_accounts.testutils import login_user_via_session

from invenio_vcs.generic_models import GenericRepository
from invenio_vcs.service import VCSService


def test_api_sync(
    app,
    client,
    test_user,
    vcs_service: VCSService,
    test_generic_repositories: list[GenericRepository],
):
    # Login the user
    login_user(test_user)
    login_user_via_session(client, email=test_user.email)

    assert len(list(vcs_service.user_available_repositories)) == 0
    res = client.post(
        url_for(
            "invenio_vcs_api.sync_user_repositories",
            provider=vcs_service.provider.factory.id,
        )
    )
    assert res.status_code == 200
    assert len(list(vcs_service.user_available_repositories)) == len(
        test_generic_repositories
    )
