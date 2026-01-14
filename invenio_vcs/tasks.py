# -*- coding: utf-8 -*-
# This file is part of Invenio.
# Copyright (C) 2025 CERN.
# Copyright (C) 2024 KTH Royal Institute of Technology.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Task for managing vcs integration."""

import datetime
from typing import TYPE_CHECKING

from celery import shared_task
from flask import current_app, g
from invenio_db import db
from invenio_i18n import gettext as _
from invenio_oauthclient.models import RemoteAccount
from invenio_oauthclient.proxies import current_oauthclient

from invenio_vcs.config import get_provider_by_id
from invenio_vcs.errors import CustomVCSReleaseNoRetryError, RepositoryAccessError
from invenio_vcs.models import Release, ReleaseStatus
from invenio_vcs.proxies import current_vcs

if TYPE_CHECKING:
    from invenio_vcs.service import VCSRelease


def _get_err_obj(msg):
    """Generate the error entry with a Sentry ID."""
    err = {"errors": msg}
    if hasattr(g, "sentry_event_id"):
        err["error_id"] = str(g.sentry_event_id)
    return err


def release_default_exception_handler(release: "VCSRelease", ex):
    """Default handler."""
    release.db_release.errors = _get_err_obj(str(ex))
    db.session.commit()


DEFAULT_ERROR_HANDLERS = [
    (CustomVCSReleaseNoRetryError, release_default_exception_handler),
    (Exception, release_default_exception_handler),
]


@shared_task(max_retries=6, default_retry_delay=10 * 60, rate_limit="100/m")
def disconnect_provider(provider_id, user_id, access_token, repo_hooks):
    """Uninstall webhooks."""
    # Note at this point the remote account and all associated data have
    # already been deleted. The celery task is passed the access_token to make
    # some last cleanup and afterwards delete itself remotely.

    # Local import to avoid circular imports
    from .service import VCSService

    try:
        # Create a nested transaction to make sure that hook deletion + token revoke is atomic
        with db.session.begin_nested():
            svc = VCSService.for_provider_and_token(provider_id, user_id, access_token)

            for repo_id, repo_hook in repo_hooks:
                if svc.disable_repository(repo_id, repo_hook):
                    current_app.logger.info(
                        _("Deleted hook from vcs repository."),
                        extra={"hook": repo_hook, "repo": repo_id},
                    )

            # If we finished our clean-up successfully, we can revoke the token
            svc.provider.revoke_token(access_token)
    except Exception as exc:
        # Retry in case vcs may be down...
        disconnect_provider.retry(exc=exc)


@shared_task(max_retries=6, default_retry_delay=10 * 60, rate_limit="100/m")
def sync_hooks(provider, user_id, repositories):
    """Sync repository hooks for a user."""
    # Local import to avoid circular imports
    from .service import VCSService

    try:
        # Sync hooks
        svc = VCSService.for_provider_and_user(provider, user_id)
        for repo_id in repositories:
            try:
                with db.session.begin_nested():
                    svc.sync_repo_hook(repo_id)
                # We commit per repository, because while the task is running
                db.session.commit()
            except RepositoryAccessError as e:
                current_app.logger.warning(str(e), exc_info=True)
                pass  # Repository not in DB yet
    except Exception as exc:
        current_app.logger.warning(str(exc), exc_info=True)
        sync_hooks.retry(exc=exc)


@shared_task(max_retries=6, default_retry_delay=10 * 60, rate_limit="100/m")
def sync_repo_users(provider, user_id, repo_provider_ids):
    """Sync the Invenio users that have access to a repo.

    A user ID is still required so we know which user's OAuth credentials to use.
    """

    from .service import VCSService

    try:
        svc = VCSService.for_provider_and_user(provider, user_id)

        for repo_id in repo_provider_ids:
            try:
                with db.session.begin_nested():
                    svc.sync_repo_users(repo_id)
                db.session.commit()
            except RepositoryAccessError as e:
                current_app.logger.warning(str(e), exc_info=True)
                pass
    except Exception as exc:
        current_app.logger.warning(str(exc), exc_info=True)
        raise sync_repo_users.retry(exc=exc)


@shared_task(ignore_result=True, max_retries=5, default_retry_delay=10 * 60)
def process_release(provider, release_id):
    """Process a received Release."""
    release_model = Release.query.filter(
        Release.provider_id == release_id,
        Release.status.in_([ReleaseStatus.RECEIVED, ReleaseStatus.FAILED]),
    ).one()

    provider = get_provider_by_id(provider).for_user(
        release_model.repository.enabled_by_user_id
    )
    release = current_vcs.release_api_class(release_model, provider)

    matched_error_cls = None
    matched_ex = None

    try:
        release.process_release()
        db.session.commit()
    except Exception as ex:
        error_handlers = current_vcs.release_error_handlers
        matched_ex = None
        for error_cls, handler in error_handlers + DEFAULT_ERROR_HANDLERS:
            if isinstance(ex, error_cls):
                handler(release, ex)
                matched_error_cls = error_cls
                matched_ex = ex
                break

    if matched_error_cls is Exception:
        process_release.retry(ex=matched_ex)


@shared_task(ignore_result=True)
def refresh_accounts(provider, expiration_threshold=None):
    """Refresh stale accounts, avoiding token expiration.

    :param expiration_threshold: Dictionary containing timedelta parameters
    referring to the maximum inactivity time.
    """
    expiration_date = datetime.datetime.now(
        tz=datetime.timezone.utc
    ) - datetime.timedelta(**(expiration_threshold or {"days": 6 * 30}))

    remote = current_oauthclient.oauth.remote_apps[provider]
    remote_accounts_to_be_updated = RemoteAccount.query.filter(
        RemoteAccount.updated < expiration_date,
        RemoteAccount.client_id == remote.consumer_key,
    )
    for remote_account in remote_accounts_to_be_updated:
        sync_account.delay(provider, remote_account.user_id)


@shared_task(ignore_result=True)
def sync_account(provider, user_id):
    """Sync a user account."""
    # Local import to avoid circular imports
    from .service import VCSService

    # Start a nested transaction so every data writing inside sync is executed atomically
    with db.session.begin_nested():
        svc = VCSService.for_provider_and_user(provider, user_id)
        svc.sync(hooks=False)
