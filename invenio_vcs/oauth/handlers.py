# -*- coding: utf-8 -*-
# This file is part of Invenio.
# Copyright (C) 2025 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

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
    """Provider-agnostic handler overrides to ensure VCS events are executed at certain points throughout the OAuth lifecyle."""

    def __init__(self, provider_factory: "RepositoryServiceProviderFactory") -> None:
        """Instance are non-user-specific."""
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
        """Disconnect callback handler for the provider."""
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
        token = svc.provider.remote_token

        if token:
            extra_data = token.remote_account.extra_data

            # Delete the token that we issued for vcs to deliver webhooks
            webhook_token_id = extra_data.get("tokens", {}).get("webhook")
            ProviderToken.query.filter_by(id=webhook_token_id).delete()

            # Disable every vcs webhooks from our side
            repos = svc.user_enabled_repositories.all()
            repos_with_hooks = []
            for repo in repos:
                if repo.enabled:
                    repos_with_hooks.append((repo.provider_id, repo.hook))
                svc.mark_repo_disabled(repo)

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
