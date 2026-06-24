# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2023-2026 CERN.
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

"""Implement OAuth client handler."""

from flask import current_app, redirect, url_for
from flask_login import current_user
from invenio_accounts.errors import AlreadyLinkedError
from invenio_accounts.models import UserIdentity
from invenio_db import db
from invenio_oauth2server.models import Token as ProviderToken
from invenio_oauthclient import oauth_link_external_id, oauth_unlink_external_id

from invenio_github.api import GitHubAPI
from invenio_github.tasks import disconnect_github, sync_account


def account_setup_handler(remote, token, resp):
    """Perform post initialization."""
    account = token.remote_account
    try:
        gh = GitHubAPI(user_id=account.user_id)
        gh.init_account()

        # Link the identity (and commit) before the repo sync, so we don't end up with
        # an unlinked account
        gh_id = str(account.extra_data["id"])
        existing = UserIdentity.query.filter_by(
            method=remote.name, id=gh_id
        ).one_or_none()
        if existing is not None and existing.id_user == account.user_id:
            return
        oauth_link_external_id(account.user, {"id": gh_id, "method": remote.name})
        db.session.commit()
    except AlreadyLinkedError:
        # The GitHub ID belongs to another user, or this user is already linked to a
        # different GitHub ID. Surface it so the OAuth flow flashes a message, and the
        # user resolves it by unlinking first.
        raise
    except Exception:
        current_app.logger.exception("Failed to link GitHub identity")
        return

    # Sync repos/hooks, and retry asynchronously on failure
    try:
        gh.sync()
        db.session.commit()
    except Exception:
        current_app.logger.exception("Failed to sync GitHub account")
        sync_account.delay(account.user_id)


def disconnect_handler(remote):
    """Disconnect callback handler for GitHub."""
    # User must be authenticated
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()

    external_method = "github"
    external_ids = [
        i.id for i in current_user.external_identifiers if i.method == external_method
    ]
    if external_ids:
        oauth_unlink_external_id(dict(id=external_ids[0], method=external_method))

    github = GitHubAPI(user_id=int(current_user.id))
    token = github.session_token

    if token:
        extra_data = token.remote_account.extra_data

        # Delete the token that we issued for GitHub to deliver webhooks
        webhook_token_id = extra_data.get("tokens", {}).get("webhook")
        ProviderToken.query.filter_by(id=webhook_token_id).delete()

        # Disable every GitHub webhooks from our side
        repos = github.user_enabled_repositories.all()
        repos_with_hooks = []
        for repo in repos:
            if repo.hook:
                repos_with_hooks.append((repo.github_id, repo.hook))
            github.disable_repo(repo)

        # Commit any changes before running the ascynhronous task
        db.session.commit()

        # Send Celery task for webhooks removal and token revocation
        disconnect_github.delay(token.access_token, repos_with_hooks)

        # Delete the RemoteAccount (along with the associated RemoteToken)
        token.remote_account.delete()
        db.session.commit()

    return redirect(url_for("invenio_oauthclient_settings.index"))
