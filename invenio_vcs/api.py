# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2023-2025 CERN.
# Copyright (C) 2024 KTH Royal Institute of Technology.
#
# Invenio is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Invenio module that adds GitHub integration to the platform."""

import json
from abc import abstractmethod
from contextlib import contextmanager
from copy import deepcopy
from urllib.parse import urlparse

import github3
import requests
from flask import current_app
from invenio_access.permissions import authenticated_user
from invenio_access.utils import get_identity
from invenio_db import db
from invenio_i18n import gettext as _
from invenio_oauth2server.models import Token as ProviderToken
from invenio_oauthclient.handlers import token_getter
from invenio_oauthclient.models import RemoteAccount, RemoteToken
from invenio_oauthclient.proxies import current_oauthclient
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.local import LocalProxy
from werkzeug.utils import cached_property

from invenio_vcs.models import Release, ReleaseStatus, Repository
from invenio_vcs.proxies import current_vcs
from invenio_vcs.tasks import sync_hooks as sync_hooks_task
from invenio_vcs.utils import iso_utcnow, parse_timestamp, utcnow

from .errors import (
    ReleaseZipballFetchError,
    RemoteAccountDataNotSet,
    RemoteAccountNotFound,
    RepositoryAccessError,
    RepositoryNotFoundError,
    UnexpectedProviderResponse,
)


class GitHubAPI(object):
    """Wrapper for GitHub API."""

    def __init__(self, remote, user_id=None):
        """Create a GitHub API object."""
        self.remote = remote
        self.user_id = user_id

    @cached_property
    def api(self):
        """Return an authenticated GitHub API."""
        return github3.login(token=self.access_token)

    @cached_property
    def access_token(self):
        """Return OAuth access token's value."""
        token = RemoteToken.get(self.user_id, self.remote.consumer_key)
        if not token:
            # The token is not yet in DB, it is retrieved from the request session.
            return self.remote.get_request_token()[0]
        return token.access_token

    @property
    def session_token(self):
        """Return OAuth session token."""
        session_token = None
        if self.user_id is not None:
            session_token = token_getter(self.remote)
        if session_token:
            token = RemoteToken.get(
                self.user_id, self.remote.consumer_key, access_token=session_token[0]
            )
            return token
        return None

    """Return OAuth remote application."""

    def check_repo_access_permissions(self, repo):
        """Checks permissions from user on repo.

        Repo has access if any of the following is True:

        - user is the owner of the repo
        - user has access to the repo in GitHub (stored in RemoteAccount.extra_data.repos)
        """
        if self.user_id and repo and repo.user_id:
            user_is_owner = repo.user_id == int(self.user_id)
            if user_is_owner:
                return True

        if self.account and self.account.extra_data:
            user_has_remote_access = self.user_available_repositories.get(
                str(repo.github_id)
            )
            if user_has_remote_access:
                return True

        raise RepositoryAccessError(
            user=self.user_id, repo=repo.name, repo_id=repo.github_id
        )

    @cached_property
    def account(self):
        """Return remote account."""
        return RemoteAccount.get(self.user_id, self.remote.consumer_key)

    @cached_property
    def webhook_url(self):
        """Return the url to be used by a GitHub webhook."""
        if not self.account.extra_data.get("tokens", {}).get("webhook"):
            raise RemoteAccountDataNotSet(
                self.user_id, _("Webhook data not found for user tokens (remote data).")
            )

        webhook_token = ProviderToken.query.filter_by(
            id=self.account.extra_data["tokens"]["webhook"]
        ).first()
        if webhook_token:
            wh_url = current_app.config.get("GITHUB_WEBHOOK_RECEIVER_URL")
            if wh_url:
                return wh_url.format(token=webhook_token.access_token)
            else:
                raise RuntimeError(_("You must set GITHUB_WEBHOOK_RECEIVER_URL."))

    def init_account(self):
        """Setup a new GitHub account."""
        if not self.account:
            raise RemoteAccountNotFound(
                self.user_id, _("Remote account was not found for user.")
            )

        ghuser = self.api.me()
        # Setup local access tokens to be used by the webhooks
        hook_token = ProviderToken.create_personal(
            "github-webhook",
            self.user_id,
            scopes=["webhooks:event"],
            is_internal=True,
        )
        # Initial structure of extra data
        self.account.extra_data = dict(
            id=ghuser.id,
            login=ghuser.login,
            name=ghuser.name,
            tokens=dict(
                webhook=hook_token.id,
            ),
            repos=dict(),
            last_sync=iso_utcnow(),
        )
        db.session.add(self.account)

    def sync(self, hooks=True, async_hooks=True):
        """Synchronize user repositories.

        :param bool hooks: True for syncing hooks.
        :param bool async_hooks: True for sending of an asynchronous task to
                                 sync hooks.

        .. note::

            Syncing happens from GitHub's direction only. This means that we
            consider the information on GitHub as valid, and we overwrite our
            own state based on this information.
        """
        github_repos = {}
        for repo in self.api.repositories():
            if repo.permissions["admin"]:
                github_repos[repo.id] = {
                    "id": repo.id,
                    "full_name": repo.full_name,
                    "description": repo.description,
                    "default_branch": repo.default_branch,
                }

        if hooks:
            self._sync_hooks(list(github_repos.keys()), asynchronous=async_hooks)

        # Update changed names for repositories stored in DB
        db_repos = Repository.query.filter(
            Repository.user_id == self.user_id,
        )

        for repo in db_repos:
            gh_repo = github_repos.get(repo.github_id)
            if gh_repo and repo.name != gh_repo["full_name"]:
                repo.name = gh_repo["full_name"]
                db.session.add(repo)

        # Remove ownership from repositories that the user has no longer
        # 'admin' permissions, or have been deleted.
        Repository.query.filter(
            Repository.user_id == self.user_id,
            ~Repository.github_id.in_(github_repos.keys()),
        ).update({"user_id": None, "hook": None}, synchronize_session=False)

        # Update repos and last sync
        self.account.extra_data.update(
            dict(
                repos=github_repos,
                last_sync=iso_utcnow(),
            )
        )
        self.account.extra_data.changed()
        db.session.add(self.account)

    def _sync_hooks(self, repos, asynchronous=True):
        """Check if a hooks sync task needs to be started."""
        if not asynchronous:
            for repo_id in repos:
                try:
                    self.sync_repo_hook(repo_id)
                except RepositoryAccessError:
                    current_app.logger.warning(
                        str(RepositoryAccessError), exc_info=True
                    )
                except NoResultFound:
                    pass  # Repository not in DB yet
        else:
            # If hooks will run asynchronously, we need to commit any changes done so far
            db.session.commit()
            sync_hooks_task.delay(self.user_id, repos)

    def _valid_webhook(self, url):
        """Check if webhook url is valid.

        The webhook url is valid if it has the same host as the configured webhook url.

        :param str url: The webhook url to be checked.
        :returns: True if the webhook url is valid, False otherwise.
        """
        if not url:
            return False
        configured_host = urlparse(self.webhook_url).netloc
        url_host = urlparse(url).netloc
        if not (configured_host and url_host):
            return False
        return configured_host == url_host

    def sync_repo_hook(self, repo_id):
        """Sync a GitHub repo's hook with the locally stored repo."""
        # Get the hook that we may have set in the past
        gh_repo = self.api.repository_with_id(repo_id)
        hooks = (
            hook
            for hook in gh_repo.hooks()
            if self._valid_webhook(hook.config.get("url", ""))
        )
        hook = next(hooks, None)

        # If hook on GitHub exists, get or create corresponding db object and
        # enable the hook. Otherwise remove the old hook information.
        repo = Repository.get(repo_id, gh_repo.full_name)

        if hook:
            if not repo:
                repo = Repository.create(self.user_id, repo_id, gh_repo.full_name)
            if not repo.enabled:
                self.enable_repo(repo, hook.id)
        else:
            if repo:
                self.disable_repo(repo)

    def check_sync(self):
        """Check if sync is required based on last sync date."""
        # If refresh interval is not specified, we should refresh every time.
        expiration = utcnow()
        refresh_td = current_app.config.get("GITHUB_REFRESH_TIMEDELTA")
        if refresh_td:
            expiration -= refresh_td
        last_sync = parse_timestamp(self.account.extra_data["last_sync"])
        return last_sync < expiration

    def create_hook(self, repo_id, repo_name):
        """Create repository hook."""
        # Create hook
        hook_config = dict(
            url=self.webhook_url,
            content_type="json",
            secret=current_app.config["GITHUB_SHARED_SECRET"],
            insecure_ssl="1" if current_app.config["GITHUB_INSECURE_SSL"] else "0",
        )

        ghrepo = self.api.repository_with_id(repo_id)
        if ghrepo:
            hooks = (
                h
                for h in ghrepo.hooks()
                if h.config.get("url", "") == hook_config["url"]
            )
            hook = next(hooks, None)

            # If hook does not exist, create one.
            if not hook:
                hook = ghrepo.create_hook(
                    "web",  # GitHub identifier for webhook service
                    hook_config,
                    events=["release"],
                )
            else:
                hook.edit(config=hook_config, events=["release"])

            if hook:
                # Get or create the repo
                repo = Repository.get(github_id=repo_id, name=repo_name)
                if not repo:
                    repo = Repository.create(self.user_id, repo_id, repo_name)

                self.enable_repo(repo, hook.id)
                return True

        return False

    def remove_hook(self, repo_id, name):
        """Remove repository hook."""
        repo = Repository.get(github_id=repo_id, name=name)

        if not repo:
            raise RepositoryNotFoundError(repo_id)

        ghrepo = self.api.repository_with_id(repo_id)
        if ghrepo:
            hooks = (
                h
                for h in ghrepo.hooks()
                if self._valid_webhook(h.config.get("url", ""))
            )
            hook = next(hooks, None)
            if not hook or hook.delete():
                self.disable_repo(repo)
                return True
        return False

    def repo_last_published_release(self, repo):
        """Retrieves the repository last release."""
        release_instance = None
        release_object = repo.latest_release(ReleaseStatus.PUBLISHED)
        if release_object:
            release_instance = current_vcs.release_api_class(release_object)
        return release_instance

    def get_repository_releases(self, repo):
        """Retrieve repository releases. Returns API release objects."""
        self.check_repo_access_permissions(repo)

        # Retrieve releases and sort them by creation date
        release_instances = []
        for release_object in repo.releases.order_by(Release.created):
            release_instance = current_vcs.release_api_class(release_object)
            release_instances.append(release_instance)

        return release_instances

    def get_user_repositories(self):
        """Retrieves user repositories, containing db repositories plus remote repositories."""
        repos = deepcopy(self.user_available_repositories)
        if repos:
            # 'Enhance' our repos dict, from our database model
            db_repos = Repository.query.filter(
                Repository.github_id.in_(
                    [int(k) for k in self.user_available_repositories.keys()]
                )
            )
            for repo in db_repos:
                if str(repo.github_id) in repos:
                    release_instance = current_vcs.release_api_class(
                        repo.latest_release()
                    )
                    repos[str(repo.github_id)]["instance"] = repo
                    repos[str(repo.github_id)]["latest"] = release_instance
        return repos

    @property
    def user_enabled_repositories(self):
        """Retrieve user repositories from the model."""
        return Repository.query.filter(Repository.user_id == self.user_id)

    @property
    def user_available_repositories(self):
        """Retrieve user repositories from user's remote data."""
        return self.account.extra_data.get("repos", {})

    def disable_repo(self, repo):
        """Disables an user repository if the user has permission to do so."""
        self.check_repo_access_permissions(repo)

        repo.hook = None
        repo.user_id = None

    def enable_repo(self, repo, hook):
        """Enables an user repository if the user has permission to do so."""
        self.check_repo_access_permissions(repo)

        repo.hook = hook
        repo.user_id = self.user_id

    def get_last_sync_time(self):
        """Retrieves the last sync delta time from github's client extra data.

        Time is computed as the delta between now and the last sync time.
        """
        if not self.account.extra_data.get("last_sync"):
            raise RemoteAccountDataNotSet(
                self.user_id, _("Last sync data is not set for user (remote data).")
            )

        extra_data = self.account.extra_data
        return extra_data["last_sync"]

    def get_repository(self, repo_name=None, repo_github_id=None):
        """Retrieves one repository.

        Checks for access permission.
        """
        repo = Repository.get(name=repo_name, github_id=repo_github_id)
        if not repo:
            raise RepositoryNotFoundError(repo_name)

        # Might raise a RepositoryAccessError
        self.check_repo_access_permissions(repo)

        return repo

    @classmethod
    def _dev_api(cls):
        """Get a developer instance for GitHub API access."""
        gh = github3.GitHub()
        gh.set_client_id(cls.remote.consumer_key, cls.remote.consumer_secret)
        return gh

    @classmethod
    def check_token(cls, token):
        """Check if an access token is authorized."""
        gh_api = cls._dev_api()
        client_id, client_secret = gh_api.session.retrieve_client_credentials()
        url = gh_api._build_url("applications", str(client_id), "token")
        with gh_api.session.temporary_basic_auth(client_id, client_secret):
            response = gh_api._post(url, data={"access_token": token})
        return response.status_code == 200

    @classmethod
    def revoke_token(cls, token):
        """Revoke an access token."""
        gh_api = cls._dev_api()
        client_id, client_secret = gh_api.session.retrieve_client_credentials()
        url = gh_api._build_url("applications", str(client_id), "token")
        with gh_api.session.temporary_basic_auth(client_id, client_secret):
            response = gh_api._delete(url, data=json.dumps({"access_token": token}))
        return response
