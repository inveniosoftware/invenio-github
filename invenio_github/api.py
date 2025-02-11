# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2023 CERN.
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
import humanize
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

from invenio_github.models import Release, ReleaseStatus, Repository
from invenio_github.proxies import current_github
from invenio_github.tasks import sync_hooks as sync_hooks_task
from invenio_github.utils import iso_utcnow, parse_timestamp, utcnow

from .errors import (
    RemoteAccountDataNotSet,
    RemoteAccountNotFound,
    RepositoryAccessError,
    RepositoryNotFoundError,
    UnexpectedGithubResponse,
)


class GitHubAPI(object):
    """Wrapper for GitHub API."""

    def __init__(self, user_id=None):
        """Create a GitHub API object."""
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

    remote = LocalProxy(
        lambda: current_oauthclient.oauth.remote_apps[
            current_app.config["GITHUB_WEBHOOK_RECEIVER_ID"]
        ]
    )
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
        ).update(dict(user_id=None, hook=None), synchronize_session=False)

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
            release_instance = current_github.release_api_class(release_object)
        return release_instance

    def get_repository_releases(self, repo):
        """Retrieve repository releases. Returns API release objects."""
        self.check_repo_access_permissions(repo)

        # Retrieve releases and sort them by creation date
        release_instances = []
        for release_object in repo.releases.order_by(Release.created):
            release_instance = current_github.release_api_class(release_object)
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
                    release_instance = current_github.release_api_class(
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


class GitHubRelease(object):
    """A GitHub release."""

    def __init__(self, release):
        """Constructor."""
        self.release_object = release

    @cached_property
    def record(self):
        """Release record."""
        return self.resolve_record()

    @cached_property
    def gh(self):
        """Return GitHubAPI object."""
        return GitHubAPI(user_id=self.event.user_id)

    @cached_property
    def event(self):
        """Get release event."""
        return self.release_object.event

    @cached_property
    def payload(self):
        """Return event payload."""
        return self.event.payload

    @cached_property
    def release_payload(self):
        """Return release metadata."""
        return self.payload["release"]

    @cached_property
    def repository_payload(self):
        """Return repository metadata."""
        return self.payload["repository"]

    @cached_property
    def repository_object(self):
        """Return repository model from database."""
        if self.release_object.repository_id:
            repository = self.release_object.repository
        else:
            repository = Repository.query.filter_by(
                user_id=self.event.user_id,
            ).one()
        return repository

    @cached_property
    def release_file_name(self):
        """Returns release zipball file name."""
        tag_name = self.release_payload["tag_name"]
        repo_name = self.repository_payload["full_name"]
        filename = f"{repo_name}-{tag_name}.zip"
        return filename

    @cached_property
    def release_zipball_url(self):
        """Returns the release zipball url."""
        return self.release_payload["zipball_url"]

    @cached_property
    def user_identity(self):
        """Generates release owner's user identity."""
        identity = get_identity(self.repository_object.user)
        identity.provides.add(authenticated_user)
        identity.user = self.repository_object.user
        return identity

    @cached_property
    def contributors(self):
        """Get list of contributors to a repository.

        The list of contributors is fetched from Github API, filtered for type "User" and sorted by contributions.

        :returns: a generator of objects that contains contributors information.
        :raises UnexpectedGithubResponse: when Github API returns a status code other than 200.
        """
        max_contributors = current_app.config.get("GITHUB_MAX_CONTRIBUTORS_NUMBER", 30)
        contributors_iter = self.gh.api.repository_with_id(
            self.repository_object.github_id
        ).contributors(number=max_contributors)

        # Consume the iterator to materialize the request and have a `last_status``.
        contributors = list(contributors_iter)
        status = contributors_iter.last_status
        if status == 200:
            # Sort by contributions and filter only users.
            sorted_contributors = sorted(
                (c for c in contributors if c.type == "User"),
                key=lambda x: x.contributions,
                reverse=True,
            )

            # Expand contributors using `Contributor.refresh()`
            contributors = [x.refresh().as_dict() for x in sorted_contributors]
            return contributors
        else:
            # Contributors fetch failed
            raise UnexpectedGithubResponse(
                _("Github returned unexpected code: %(status)s for release %(repo_id)s")
                % {"status": status, "repo_id": self.repository_object.github_id}
            )

    @cached_property
    def owner(self):
        """Get owner of repository as a creator."""
        try:
            owner = self.gh.api.repository_with_id(
                self.repository_object.github_id
            ).owner
            return owner
        except Exception:
            return None

    # Helper functions

    def is_first_release(self):
        """Checks whether the current release is the first release of the repository."""
        latest_release = self.repository_object.latest_release(ReleaseStatus.PUBLISHED)
        return True if not latest_release else False

    def test_zipball(self):
        """Extract files to download from GitHub payload."""
        zipball_url = self.release_payload["zipball_url"]

        # Execute a HEAD request to the zipball url to test the url.
        response = self.gh.api.session.head(zipball_url, allow_redirects=True)

        # In case where there is a tag and branch with the same name, we might
        # get back a "300 Mutliple Choices" response, which requires fetching
        # an "alternate" link.
        if response.status_code == 300:
            zipball_url = response.links.get("alternate", {}).get("url")
            if zipball_url:
                response = self.gh.api.session.head(zipball_url, allow_redirects=True)
                # Another edge-case, is when the access token we have does not
                # have the scopes/permissions to access public links. In that
                # rare case we fallback to a non-authenticated request.
                if response.status_code == 404:
                    response = requests.head(zipball_url, allow_redirects=True)
                    # If this response is successful we want to use the finally
                    # resolved URL to fetch the ZIP from.
                    if response.status_code == 200:
                        zipball_url = response.url

        assert (
            response.status_code == 200
        ), f"Could not retrieve archive from GitHub: {zipball_url}"

    # High level API

    def release_failed(self):
        """Set release status to FAILED."""
        self.release_object.status = ReleaseStatus.FAILED

    def release_processing(self):
        """Set release status to PROCESSING."""
        self.release_object.status = ReleaseStatus.PROCESSING

    def release_published(self):
        """Set release status to PUBLISHED."""
        self.release_object.status = ReleaseStatus.PUBLISHED

    def retrieve_remote_file(self, file_name):
        """Retrieves a file from the repository, for the current release, using the github client.

        :param file_name: the name of the file to be retrieved from the repository.
        :returns: the file contents or None, if the file if not fetched.
        """
        gh_repo_owner = self.repository_payload["owner"]["login"]
        gh_repo_name = self.repository_payload["name"]
        gh_tag_name = self.release_payload["tag_name"]
        try:
            content = self.gh.api.repository(gh_repo_owner, gh_repo_name).file_contents(
                path=file_name, ref=gh_tag_name
            )
        except github3.exceptions.NotFoundError:
            # github3 raises a github3.exceptions.NotFoundError if the file is not found
            return None
        return content

    @contextmanager
    def fetch_zipball_file(self):
        """Fetch release zipball file using the current github session."""
        session = self.gh.api.session
        timeout = current_app.config.get("GITHUB_ZIPBALL_TIMEOUT", 300)
        with session.get(self.release_zipball_url, stream=True, timeout=timeout) as s:
            yield s.raw

    def publish(self):
        """Publish a GitHub release."""
        raise NotImplementedError

    def process_release(self):
        """Processes a github release."""
        raise NotImplementedError

    def resolve_record(self):
        """Resolves a record from the release. To be implemented by the API class implementation."""
        raise NotImplementedError

    def serialize_record(self):
        """Serializes the release record."""
        raise NotImplementedError

    @property
    @abstractmethod
    def badge_title(self):
        """Stores a string to render in the record badge title (e.g. 'DOI')."""
        return None

    @property
    @abstractmethod
    def badge_value(self):
        """Stores a string to render in the record badge value (e.g. '10.1234/invenio.1234')."""
        raise NotImplementedError

    @property
    def record_url(self):
        """Release self url (e.g. github HTML url)."""
        raise NotImplementedError
