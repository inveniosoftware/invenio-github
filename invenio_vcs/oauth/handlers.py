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

"""Implement OAuth client handler."""

import typing

from flask import current_app, redirect, url_for
from flask_login import current_user
from invenio_db import db
from invenio_oauth2server.models import Token as ProviderToken
from invenio_oauthclient import oauth_unlink_external_id

from invenio_vcs.service import VCSService
from invenio_vcs.tasks import disconnect_provider

if typing.TYPE_CHECKING:
    from invenio_vcs.providers import RepositoryServiceProviderFactory


class OAuthHandlers:
    def __init__(self, provider_factory: "RepositoryServiceProviderFactory") -> None:
        self.provider_factory = provider_factory

    def account_setup_handler(self, remote, token, resp):
        """Perform post initialization."""
        try:
            svc = VCSService(
                self.provider_factory.for_user(token.remote_account.user_id)
            )
            svc.init_account()
            svc.sync()
            db.session.commit()
        except Exception as e:
            current_app.logger.warning(str(e), exc_info=True)

    def disconnect_handler(self, remote):
        """Disconnect callback handler for GitHub."""
        # User must be authenticated
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()

        external_method = self.provider_factory.id
        external_ids = [
            i.id
            for i in current_user.external_identifiers
            if i.method == external_method
        ]
        if external_ids:
            oauth_unlink_external_id(dict(id=external_ids[0], method=external_method))

        svc = VCSService(self.provider_factory.for_user(current_user.id))
        token = svc.provider.session_token

        if token:
            extra_data = token.remote_account.extra_data

            # Delete the token that we issued for GitHub to deliver webhooks
            webhook_token_id = extra_data.get("tokens", {}).get("webhook")
            ProviderToken.query.filter_by(id=webhook_token_id).delete()

            # Disable every GitHub webhooks from our side
            repos = svc.user_enabled_repositories.all()
            repos_with_hooks = []
            for repo in repos:
                if repo.hook:
                    repos_with_hooks.append((repo.provider_id, repo.hook))
                svc.disable_repository(repo.id)

            # Commit any changes before running the ascynhronous task
            db.session.commit()

            # Send Celery task for webhooks removal and token revocation
            disconnect_provider.delay(
                self.provider_factory.id,
                current_user.id,
                token.access_token,
                repos_with_hooks,
            )

            # Delete the RemoteAccount (along with the associated RemoteToken)
            token.remote_account.delete()
            db.session.commit()

        return redirect(url_for("invenio_oauthclient_settings.index"))
