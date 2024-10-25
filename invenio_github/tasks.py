# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2023 CERN.
# Copyright (C) 2024 KTH Royal Institute of Technology.
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

"""Task for managing GitHub integration."""

import datetime

import github3
from celery import shared_task
from flask import current_app, g
from invenio_db import db
from invenio_i18n import gettext as _
from invenio_oauthclient.models import RemoteAccount
from invenio_oauthclient.proxies import current_oauthclient

from invenio_github.errors import CustomGitHubMetadataError, RepositoryAccessError
from invenio_github.models import Release, ReleaseStatus
from invenio_github.proxies import current_github


def _get_err_obj(msg):
    """Generate the error entry with a Sentry ID."""
    err = {"errors": msg}
    if hasattr(g, "sentry_event_id"):
        err["error_id"] = str(g.sentry_event_id)
    return err


def release_gh_metadata_handler(release, ex):
    """Handler for CustomGithubMetadataError."""
    release.release_object.errors = _get_err_obj(str(ex))
    db.session.commit()


def release_default_exception_handler(release, ex):
    """Default handler."""
    release.release_object.errors = _get_err_obj(str(ex))
    db.session.commit()


DEFAULT_ERROR_HANDLERS = [
    (CustomGitHubMetadataError, release_gh_metadata_handler),
    (Exception, release_default_exception_handler),
]


@shared_task(max_retries=6, default_retry_delay=10 * 60, rate_limit="100/m")
def disconnect_github(access_token, repo_hooks):
    """Uninstall webhooks."""
    # Note at this point the remote account and all associated data have
    # already been deleted. The celery task is passed the access_token to make
    # some last cleanup and afterwards delete itself remotely.

    # Local import to avoid circular imports
    from .api import GitHubAPI

    try:
        # Create a nested transaction to make sure that hook deletion + token revoke is atomic
        with db.session.begin_nested():
            gh = github3.login(token=access_token)
            for repo_id, repo_hook in repo_hooks:
                ghrepo = gh.repository_with_id(repo_id)
                if ghrepo:
                    hook = ghrepo.hook(repo_hook)
                    if hook and hook.delete():
                        current_app.logger.info(
                            _("Deleted hook from github repository."),
                            extra={"hook": hook.id, "repo": ghrepo.full_name},
                        )
            # If we finished our clean-up successfully, we can revoke the token
            GitHubAPI.revoke_token(access_token)
    except Exception as exc:
        # Retry in case GitHub may be down...
        disconnect_github.retry(exc=exc)


@shared_task(max_retries=6, default_retry_delay=10 * 60, rate_limit="100/m")
def sync_hooks(user_id, repositories):
    """Sync repository hooks for a user."""
    # Local import to avoid circular imports
    from .api import GitHubAPI

    try:
        # Sync hooks
        gh = GitHubAPI(user_id=user_id)
        for repo_id in repositories:
            try:
                with db.session.begin_nested():
                    gh.sync_repo_hook(repo_id)
                # We commit per repository, because while the task is running
                db.session.commit()
            except RepositoryAccessError as e:
                current_app.logger.warning(str(e), exc_info=True)
                pass  # Repository not in DB yet
    except Exception as exc:
        current_app.logger.warning(str(exc), exc_info=True)
        sync_hooks.retry(exc=exc)


@shared_task(ignore_result=True, max_retries=5, default_retry_delay=10 * 60)
def process_release(release_id):
    """Process a received Release."""
    release_model = Release.query.filter(
        Release.release_id == release_id,
        Release.status.in_([ReleaseStatus.RECEIVED, ReleaseStatus.FAILED]),
    ).one()

    release = current_github.release_api_class(release_model)

    matched_error_cls = None
    matched_ex = None

    try:
        release.process_release()
        db.session.commit()
    except Exception as ex:
        error_handlers = current_github.release_error_handlers
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
def refresh_accounts(expiration_threshold=None):
    """Refresh stale accounts, avoiding token expiration.

    :param expiration_threshold: Dictionary containing timedelta parameters
    referring to the maximum inactivity time.
    """
    expiration_date = datetime.datetime.utcnow() - datetime.timedelta(
        **(expiration_threshold or {"days": 6 * 30})
    )

    remote = current_oauthclient.oauth.remote_apps["github"]
    remote_accounts_to_be_updated = RemoteAccount.query.filter(
        RemoteAccount.updated < expiration_date,
        RemoteAccount.client_id == remote.consumer_key,
    )
    for remote_account in remote_accounts_to_be_updated:
        sync_account.delay(remote_account.user_id)


@shared_task(ignore_result=True)
def sync_account(user_id):
    """Sync a user account."""
    # Local import to avoid circular imports
    from .api import GitHubAPI

    # Start a nested transaction so every data writing inside sync is executed atomically
    with db.session.begin_nested():
        gh = GitHubAPI(user_id=user_id)
        gh.sync(hooks=False, async_hooks=False)
