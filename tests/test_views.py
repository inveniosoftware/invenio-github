# -*- coding: utf-8 -*-
#
# Copyright (C) 2023 CERN.
#
# Invenio-Github is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
"""Test invenio-github views."""
from flask_security import login_user
from invenio_accounts.testutils import login_user_via_session
from invenio_oauthclient.models import RemoteAccount


def test_api_init_user(app, client, github_api, test_user):
    # Login the user
    login_user(test_user)
    login_user_via_session(client, email=test_user.email)

    # Initialise user account
    res = client.post("/user/github", follow_redirects=True)
    assert res.status_code == 200

    # Validate RemoteAccount exists between querying it
    remote_accounts = RemoteAccount.query.filter_by(user_id=test_user.id).all()
    assert len(remote_accounts) == 1
    remote_account = remote_accounts[0]

    # Account init adds user's github data to its remote account extra data
    assert remote_account.extra_data
    assert len(remote_account.extra_data.keys())
