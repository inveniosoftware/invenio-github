# -*- coding: utf-8 -*-
# This file is part of Invenio.
# Copyright (C) 2025 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""Contrib provider implementation for GitHub."""

import json

import dateutil
import github3
import requests
from flask import current_app
from github3.repos import ShortRepository
from invenio_i18n import gettext as _
from invenio_oauthclient.contrib.github import GitHubOAuthSettingsHelper
from werkzeug.utils import cached_property

from invenio_vcs.errors import ReleaseZipballFetchError, VCSTokenNotFound
from invenio_vcs.generic_models import (
    GenericContributor,
    GenericOwner,
    GenericOwnerType,
    GenericRelease,
    GenericRepository,
    GenericUser,
    GenericWebhook,
)
from invenio_vcs.providers import (
    RepositoryServiceProvider,
    RepositoryServiceProviderFactory,
)


class GitHubProviderFactory(RepositoryServiceProviderFactory):
    """Contrib implementation factory for VCS."""

    def __init__(
        self,
        base_url,
        webhook_receiver_url,
        id="github",
        name="GitHub",
        description="Automatically archive your repositories",
        credentials_key="GITHUB_APP_CREDENTIALS",
        config={},
    ):
        """Initialise with GitHub-specific defaults."""
        super().__init__(
            GitHubProvider,
            base_url=base_url,
            webhook_receiver_url=webhook_receiver_url,
            id=id,
            name=name,
            description=description,
            credentials_key=credentials_key,
            icon="github",
            repository_name="repository",
            repository_name_plural="repositories",
            release_docs_link="https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository",
            repo_list_message="If your organization's repositories do not show up in the list, please ensure you have enabled third-party access.",
            repo_list_info_link="https://docs.github.com/en/organizations/managing-oauth-access-to-your-organizations-data/approving-oauth-apps-for-your-organization",
        )

        self._config = dict()
        self._config.update(
            shared_secret="",
            insecure_ssl=False,
        )
        self._config.update(config)

    def update_config_with_override(self, config_override: dict):
        """Allow overriding GitHub-specific config options."""
        super().update_config_override(config_override)
        self._config.update(config_override.get("config", {}))

    @property
    def remote_config(self):
        """
        Use the existing GitHub OAuth client implementation in invenio-oauthclient with some minor modifications.

        We are keeping this client in invenio-oauthclient for backwards-compatibility and because some installations
        may already be using GitHub OAuth as a login method without the full integration.
        """
        request_token_params = {
            # General `repo` scope is required for reading collaborators
            # https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps
            "scope": "read:user,user:email,admin:repo_hook,read:org,repo"
        }

        helper = GitHubOAuthSettingsHelper(
            title=self.name,
            icon="fa fa-{}".format(self.icon),
            description=self.description,
            base_url=self.base_url,
            app_key=self.credentials_key,
        )
        github_app = helper.remote_app
        github_app["disconnect_handler"] = self.oauth_handlers.disconnect_handler
        github_app["signup_handler"][
            "setup"
        ] = self.oauth_handlers.account_setup_handler
        github_app["params"]["request_token_params"] = request_token_params

        return github_app

    @property
    def config(self):
        """Returns the GitHub-specific config dict."""
        return self._config

    def webhook_is_create_release_event(self, event_payload):
        """Three possible event types can correspond to a create release event."""
        action = event_payload.get("action")
        is_draft_release = event_payload.get("release", {}).get("draft")

        # Draft releases do not create releases on invenio
        is_create_release_event = (
            action in ("published", "released", "created") and not is_draft_release
        )
        return is_create_release_event

    @staticmethod
    def _extract_license(gh_repo_dict):
        """
        The GitHub API returns the `license` as a simple key of the ShortRepository.

        But for some reason github3py does not include a mapping for this.
        So the only way to access it without making an additional request is to convert
        the repo to a dict.
        """
        license_obj = gh_repo_dict.get("license")
        if license_obj is not None:
            spdx = license_obj["spdx_id"]
            if spdx == "NOASSERTION":
                # For 'other' type of licenses, Github sets the spdx_id to NOASSERTION
                return None
            return spdx
        return None

    def webhook_event_to_generic(self, event_payload):
        """Convert the webhook payload to a generic release and repository without making additional API calls and using just the payload data."""
        release_published_at = event_payload["release"].get("published_at")
        if release_published_at is not None:
            release_published_at = dateutil.parser.parse(release_published_at)

        release = GenericRelease(
            id=str(event_payload["release"]["id"]),
            name=event_payload["release"].get("name"),
            tag_name=event_payload["release"]["tag_name"],
            tarball_url=event_payload["release"].get("tarball_url"),
            zipball_url=event_payload["release"].get("zipball_url"),
            body=event_payload["release"].get("body"),
            created_at=dateutil.parser.parse(event_payload["release"]["created_at"]),
            published_at=release_published_at,
        )

        license_spdx = GitHubProviderFactory._extract_license(
            event_payload["repository"]
        )

        repo = GenericRepository(
            id=str(event_payload["repository"]["id"]),
            full_name=event_payload["repository"]["full_name"],
            description=event_payload["repository"].get("description"),
            default_branch=event_payload["repository"]["default_branch"],
            license_spdx=license_spdx,
        )

        return (release, repo)

    def url_for_repository(self, repository_name: str) -> str:
        """URL to view a repository."""
        return "{}/{}".format(self.base_url, repository_name)

    def url_for_release(
        self, repository_name: str, release_id: str, release_tag: str
    ) -> str:
        """URL to view a release."""
        return "{}/{}/releases/tag/{}".format(
            self.base_url, repository_name, release_tag
        )

    def url_for_tag(self, repository_name: str, tag_name: str):
        """URL to view a tag."""
        return "{}/{}/tree/{}".format(self.base_url, repository_name, tag_name)

    def url_for_new_release(self, repository_name: str):
        """URL for creating a new release."""
        return "{}/{}/releases/new".format(self.base_url, repository_name)

    def url_for_new_file(self, repository_name: str, branch_name: str, file_name: str):
        """URL for creating a new file in the web editor."""
        return "{}/{}/new/{}?filename={}".format(
            self.base_url, repository_name, branch_name, file_name
        )

    def url_for_new_repo(self) -> str:
        """URL for creating a new repository."""
        return "{}/new".format(self.base_url)


class GitHubProvider(RepositoryServiceProvider):
    """Contrib user-specific implementation for GitHub."""

    @cached_property
    def _gh(self):
        """Initialise the GitHub API object (either for public or enterprise self-hosted GitHub)."""
        if self.remote_token is None:
            raise VCSTokenNotFound

        _gh = None
        if self.factory.base_url == "https://github.com":
            _gh = github3.login(token=self.remote_token.access_token)
        else:
            _gh = github3.enterprise_login(
                url=self.factory.base_url, token=self.remote_token.access_token
            )

        # login can return None if it's unsuccessful.
        assert _gh is not None
        return _gh

    def list_repositories(self):
        """List the user's top repos."""
        repos: dict[str, GenericRepository] = {}
        for repo in self._gh.repositories():
            assert isinstance(repo, ShortRepository)

            if repo.permissions["admin"]:
                repos[str(repo.id)] = GenericRepository(
                    id=str(repo.id),
                    full_name=repo.full_name,
                    description=repo.description,
                    default_branch=repo.default_branch,
                    license_spdx=GitHubProviderFactory._extract_license(repo.as_dict()),
                )

        return repos

    def list_repository_webhooks(self, repository_id):
        """List a repo's webhooks."""
        assert repository_id.isdigit()
        repo = self._gh.repository_with_id(int(repository_id))
        if repo is None:
            return None

        hooks = []
        for hook in repo.hooks():
            hooks.append(
                GenericWebhook(
                    id=str(hook.id),
                    repository_id=repository_id,
                    url=hook.config.get("url"),
                )
            )
        return hooks

    def list_repository_user_ids(self, repository_id: str):
        """List the admin collaborator User IDs of a repository."""
        assert repository_id.isdigit()
        repo = self._gh.repository_with_id(int(repository_id))
        if repo is None:
            return None

        user_ids: list[str] = []
        # This API route has a `permission` param but it's not supported by github3.py
        # https://docs.github.com/en/rest/collaborators/collaborators?apiVersion=2022-11-28#list-repository-collaborators
        for collaborator in repo.collaborators():
            if not collaborator.permissions["admin"]:
                continue

            user_ids.append(str(collaborator.id))

        return user_ids

    def get_repository(self, repository_id):
        """Get a single repository."""
        assert repository_id.isdigit()

        repo = self._gh.repository_with_id(int(repository_id))
        if repo is None:
            return None

        return GenericRepository(
            id=str(repo.id),
            full_name=repo.full_name,
            description=repo.description,
            default_branch=repo.default_branch,
            license_spdx=GitHubProviderFactory._extract_license(repo.as_dict()),
        )

    def create_webhook(self, repository_id):
        """Create a webhook using some custom GitHub-specific config options."""
        assert repository_id.isdigit()

        hook_config = dict(
            url=self.webhook_url,
            content_type="json",
            secret=self.factory.config["shared_secret"],
            insecure_ssl="1" if self.factory.config["insecure_ssl"] else "0",
        )

        repo = self._gh.repository_with_id(int(repository_id))
        if repo is None:
            return None

        hooks = (h for h in repo.hooks() if h.config.get("url", "") == self.webhook_url)
        hook = next(hooks, None)

        if not hook:
            hook = repo.create_hook("web", hook_config, events=["release"])
        else:
            hook.edit(config=hook_config, events=["release"])

        return str(hook.id)

    def delete_webhook(self, repository_id, hook_id=None):
        """Delete a webhook."""
        assert repository_id.isdigit()

        repo = self._gh.repository_with_id(int(repository_id))
        if repo is None:
            return False

        if hook_id is not None:
            hook = repo.hook(hook_id)
        else:
            hooks = (
                h
                for h in repo.hooks()
                if self.is_valid_webhook(h.config.get("url", ""))
            )
            hook = next(hooks, None)

        if not hook or hook.delete():
            return True
        return False

    def get_own_user(self):
        """Get the currently logged in user."""
        user = self._gh.me()
        if user is not None:
            return GenericUser(str(user.id), user.login, user.name)

        return None

    def list_repository_contributors(self, repository_id, max):
        """List and sort (by contribution count) the contributors of a repo."""
        assert repository_id.isdigit()

        repo = self._gh.repository_with_id(int(repository_id))
        if repo is None:
            return None

        contributors = []
        for c in repo.contributors(number=max):
            contributions_count = c.contributions_count
            c = c.refresh()
            contributors.append(
                GenericContributor(
                    id=str(c.id),
                    username=c.login,
                    display_name=c.name,
                    contributions_count=contributions_count,
                    company=c.company,
                )
            )

        return contributors

    def get_repository_owner(self, repository_id):
        """Get the owner of a repo."""
        assert repository_id.isdigit()

        repo = self._gh.repository_with_id(int(repository_id))
        if repo is None:
            return None

        owner_type = (
            GenericOwnerType.Person
            if repo.owner.type == "User"
            else GenericOwnerType.Organization
        )

        return GenericOwner(
            id=str(repo.owner.id),
            path_name=repo.owner.login,
            type=owner_type,
            # GitHub API does not return the display name for the owner
        )

    def resolve_release_zipball_url(self, release_zipball_url):
        """Handle some GitHub-specific quirks related to URL authentication."""
        url = release_zipball_url

        # Execute a HEAD request to the zipball url to test if it is accessible.
        response = self._gh.session.head(url, allow_redirects=True)

        # In case where there is a tag and branch with the same name, we might get back
        # a "300 Multiple Choices" response, which requires fetching an "alternate"
        # link.
        if response.status_code == 300:
            alternate_url = response.links.get("alternate", {}).get("url")
            if alternate_url:
                url = alternate_url  # Use the alternate URL
                response = self._gh.session.head(url, allow_redirects=True)

        # Another edge-case, is when the access token we have does not have the
        # scopes/permissions to access public links. In that rare case we fallback to a
        # non-authenticated request.
        if response.status_code == 404:
            current_app.logger.warning(
                "GitHub zipball URL {url} not found, trying unauthenticated request.",
                extra={"url": response.url},
            )
            response = requests.head(url, allow_redirects=True)
            # If this response is successful we want to use the finally resolved URL to
            # fetch the ZIP from.
            if response.status_code == 200:
                return response.url

        if response.status_code != 200:
            raise ReleaseZipballFetchError()

        return response.url

    def fetch_release_zipball(self, release_zipball_url, timeout):
        """Fetch a specific release artifact file using a raw authenticated API request."""
        with self._gh.session.get(
            release_zipball_url, stream=True, timeout=timeout
        ) as resp:
            yield resp.raw

    def retrieve_remote_file(self, repository_id, ref_name, file_name):
        """Retrieve a specific file from the repo via the API."""
        assert repository_id.isdigit()

        try:
            resp = self._gh.repository_with_id(int(repository_id)).file_contents(
                path=file_name, ref=ref_name
            )
            return resp.decoded
        except github3.exceptions.NotFoundError:
            return None

    def revoke_token(self, access_token):
        """Delete the specified access token using a custom API request."""
        client_id, client_secret = self._gh.session.retrieve_client_credentials()
        url = self._gh._build_url("applications", str(client_id), "token")
        with self._gh.session.temporary_basic_auth(client_id, client_secret):
            response = self._gh._delete(
                url, data=json.dumps({"access_token": access_token})
            )
        return response
