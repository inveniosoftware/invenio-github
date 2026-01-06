# -*- coding: utf-8 -*-
# This file is part of Invenio.
# Copyright (C) 2025 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Abstract classes to be implemented for each provider."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generator
from urllib.parse import urlparse

from invenio_i18n import gettext as _
from invenio_oauth2server.models import Token as ProviderToken
from invenio_oauthclient import current_oauthclient
from invenio_oauthclient.models import RemoteAccount, RemoteToken
from urllib3 import HTTPResponse
from werkzeug.local import LocalProxy
from werkzeug.utils import cached_property

from invenio_vcs.errors import RemoteAccountDataNotSet
from invenio_vcs.generic_models import (
    GenericContributor,
    GenericOwner,
    GenericRelease,
    GenericRepository,
    GenericUser,
    GenericWebhook,
)
from invenio_vcs.oauth.handlers import OAuthHandlers


class RepositoryServiceProviderFactory(ABC):
    """
    A factory to create user-specific VCS providers.

    This class is instantiated once per instance,
    usually in the `invenio.cfg` file. It contains general settings and methods that are impossible
    to generalise and must be specified on a provider-specific level.

    All methods within this class (except the constructor and update_config_override) should be pure functions.
    """

    def __init__(
        self,
        provider: type["RepositoryServiceProvider"],
        base_url: str,
        webhook_receiver_url: str,
        id: str,
        name: str,
        description: str,
        icon: str,
        credentials_key: str,
        repository_name: str,
        repository_name_plural: str,
        release_docs_link: str,
        repo_list_message: str | None = None,
        repo_list_info_link: str | None = None,
    ):
        """Initialize the repository service provider factory."""

        self.provider = provider
        self.base_url = base_url
        self.webhook_receiver_url = webhook_receiver_url
        self.id = id
        self.name = name
        self.description = description
        self.icon = icon
        self.credentials_key = credentials_key
        self.repository_name = repository_name
        self.repository_name_plural = repository_name_plural
        self.release_docs_link = release_docs_link
        self.repo_list_message = repo_list_message
        self.repo_list_info_link = repo_list_info_link

    def update_config_override(self, config_override: dict):
        """After the application is initialised, this method is called to override the provider configuration using VCS_PROVIDER_CONFIG_DICT if specified.

        This cannot happen in the constructor, as we don't have access to other config variables there yet since the app is not initialised.
        """
        self.base_url = config_override.get("base_url", self.base_url)
        self.webhook_receiver_url = config_override.get(
            "webhook_receiver_url", self.webhook_receiver_url
        )
        self.name = config_override.get("name", self.name)
        self.description = config_override.get("description", self.description)
        self.icon = config_override.get("icon", self.icon)
        self.credentials_key = config_override.get(
            "credentials_key", self.credentials_key
        )
        self.repository_name = config_override.get(
            "repository_name", self.repository_name
        )
        self.repository_name_plural = config_override.get(
            "repository_name_plural", self.repository_name_plural
        )
        self.release_docs_link = config_override.get(
            "release_docs_links", self.release_docs_link
        )
        self.repo_list_message = config_override.get(
            "repo_list_message", self.repo_list_message
        )
        self.repo_list_info_link = config_override.get(
            "repo_list_info_link", self.repo_list_info_link
        )

    @property
    @abstractmethod
    def remote_config(self) -> dict[str, Any]:
        """
        Returns a dictionary as the config of the OAuth remote app for this provider.

        The config of the app is usually based on the config variables provided
        in the constructor.
        """
        raise NotImplementedError

    @property
    def oauth_handlers(self):
        """OAuth client handlers (for invenio-oauthclient) specific to the provider."""
        return OAuthHandlers(self)

    @cached_property
    def remote(self):
        """The corresponding remote OAuth client app."""
        return LocalProxy(lambda: current_oauthclient.oauth.remote_apps[self.id])

    @property
    @abstractmethod
    def config(self) -> dict:
        """Returns a configuration dictionary with options that are specific to a given provider."""
        raise NotImplementedError

    @abstractmethod
    def url_for_repository(self, repository_name: str) -> str:
        """Generates the URL for the UI homepage of a repository."""
        raise NotImplementedError

    @abstractmethod
    def url_for_release(
        self, repository_name: str, release_id: str, release_tag: str
    ) -> str:
        """Generates the URL for the UI page of the details of a release."""
        raise NotImplementedError

    @abstractmethod
    def url_for_tag(self, repository_name: str, tag_name: str) -> str:
        """
        Generates the URL for the UI page showing the file tree for the latest commit with a given named tag.

        If the VCS does not implement a separate page for the release details and its tree, then `url_for_release` may
        return the same value as `url_for_tag`.
        """
        raise NotImplementedError

    @abstractmethod
    def url_for_new_release(self, repository_name: str) -> str:
        """Generates the URL for the UI page through which the user can create a new release for a specific repository."""
        raise NotImplementedError

    @abstractmethod
    def url_for_new_file(
        self, repository_name: str, branch_name: str, file_name: str
    ) -> str:
        """
        Generates the URL for the UI pages through which a new file with a specific name on a specific branch in a specific repository can be created.

        Usually, this allows the user to type the file contents directly or upload an existing file.
        """
        raise NotImplementedError

    @abstractmethod
    def url_for_new_repo(self) -> str:
        """Generates the URL for the UI page through which a new repository can be created."""
        raise NotImplementedError

    @abstractmethod
    def webhook_is_create_release_event(self, event_payload: dict[str, Any]):
        """
        Returns whether the raw JSON payload of a webhook event is an event corresponding to the publication of a webhook.

        Returning False will end further processing of the event.
        """
        raise NotImplementedError

    @abstractmethod
    def webhook_event_to_generic(
        self, event_payload: dict[str, Any]
    ) -> tuple[GenericRelease, GenericRepository]:
        """Returns the data of the release and repository as extracted from the raw JSON payload of a webhook event, in generic form."""
        raise NotImplementedError

    def for_user(self, user_id: int):
        """Creates a provider for a specific user, taking the access token from the DB."""
        return self.provider(self, user_id)

    def for_access_token(self, user_id: int, access_token: str):
        """Creates a provider for a specific user, taking the access token directly as an argument."""
        return self.provider(self, user_id, access_token=access_token)

    @property
    def vocabulary(self):
        """UI terminology (and icon) for the provider."""
        return {
            "id": self.id,
            "name": self.name,
            "repository_name": self.repository_name,
            "repository_name_plural": self.repository_name_plural,
            "release_docs_link": self.release_docs_link,
            "repo_list_message": self.repo_list_message,
            "repo_list_info_link": self.repo_list_info_link,
            "icon": self.icon,
        }


class RepositoryServiceProvider(ABC):
    """
    The methods to interact with the API of a VCS provider.

    This class is user-specific and is always created from a `RepositoryServiceProviderFactory`.

    While some of the default method implementations (such as `access_token`) make access to
    the DB, overrides of the unimplemented methods should avoid doing so to minimise
    unexpected behaviour. Interaction should be solely with the API of the VCS provider.

    Providers must currently support all of these operations.
    """

    def __init__(
        self, factory: RepositoryServiceProviderFactory, user_id: int, access_token=None
    ) -> None:
        """
        Internal method for constructing the provider.

        It's recommended to use `for_user` in the factory instead.
        """
        self.factory = factory
        self.user_id = user_id
        self._access_token = access_token

    @cached_property
    def remote_account(self):
        """Returns the OAuth Remote Account corresponding to the user's authentication with the provider."""
        return RemoteAccount.get(self.user_id, self.factory.remote.consumer_key)

    @cached_property
    def remote_token(self):
        """Return OAuth remote token model."""
        if self._access_token is not None:
            return self._access_token

        token = RemoteToken.get(self.user_id, self.factory.remote.consumer_key)

        if token is None:
            return None

        if token.is_expired:
            token.refresh_access_token()

        return token

    @cached_property
    def webhook_url(self):
        """
        Returns a formatted version of the webhook receiver URL specified in the provider factory.

        The `{token}` variable in this URL string is replaced with the user-specific
        webhook token.
        """
        if not self.remote_account.extra_data.get("tokens", {}).get("webhook"):
            raise RemoteAccountDataNotSet(
                self.user_id, _("Webhook data not found for user tokens (remote data).")
            )

        webhook_token = ProviderToken.query.filter_by(
            id=self.remote_account.extra_data["tokens"]["webhook"]
        ).first()
        if webhook_token:
            return self.factory.webhook_receiver_url.format(
                token=webhook_token.access_token
            )

    def is_valid_webhook(self, url: str | None):
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

    @abstractmethod
    def list_repositories(self) -> dict[str, GenericRepository] | None:
        """
        Returns a dictionary of {repository_id: GenericRepository} for the current user.

        This should return _all_ repositories for which the user has permission
        to create and delete webhooks.

        This means this function could return extremely large dictionaries in some cases,
        but it will only be called during irregular sync events and stored in the DB.
        """
        raise NotImplementedError

    @abstractmethod
    def list_repository_webhooks(
        self, repository_id: str
    ) -> list[GenericWebhook] | None:
        """
        Returns an arbitrarily ordered list of the current webhooks of a repository.

        This list should only include active webhooks which generate events for which
        the corresponding `RepositoryServiceProviderFactory.webhook_is_create_release_event`
        would return True.
        """
        raise NotImplementedError

    def get_first_valid_webhook(self, repository_id: str) -> GenericWebhook | None:
        """Get the first webhook for which `is_valid_webhook` is true."""
        webhooks = self.list_repository_webhooks(repository_id)
        if webhooks is None:
            return None
        for hook in webhooks:
            if self.is_valid_webhook(hook.url):
                return hook
        return None

    @abstractmethod
    def get_repository(self, repository_id: str) -> GenericRepository | None:
        """Returns the details of a specific repository by ID, or None if the repository does not exist or the user has no permission to view it."""
        raise NotImplementedError

    @abstractmethod
    def list_repository_contributors(
        self, repository_id: str, max: int
    ) -> list[GenericContributor] | None:
        """
        Returns the list of entities that have contributed to a given repository.

        This list may contain entities that are not currently or have never been
        registered users of the VCS provider (e.g. in the case of repos imported
        from a remote source). The order of the list is arbitrary, and it may include
        non-human contributors (e.g. automated tools or organisations).

        Returns None if the repository does not exist or the user has no permission
        to view it or its contributors.
        """
        raise NotImplementedError

    @abstractmethod
    def list_repository_user_ids(self, repository_id: str) -> list[str] | None:
        """
        Returns a list of the IDs of valid users registered with the VCS provider that have sufficient permission to create/delete webhooks on the given repository.

        This list should contain all users for which the corresponding
        repo would be included in a `list_repositories` call.

        Returns None if the repository does not exist or the user has no permission
        to view it or its member users.
        """
        raise NotImplementedError

    @abstractmethod
    def get_repository_owner(self, repository_id: str) -> GenericOwner | None:
        """
        Returns the 'owner' of a repository, which is either a user or a group/organization.

        Returns None if the repository does not exist or the user does not have permission
        to find out its owner.
        """
        raise NotImplementedError

    @abstractmethod
    def create_webhook(self, repository_id: str) -> str | None:
        """
        Creates a new webhook for a given repository, trigerred by a "create release" event.

        The URL destination is specified by `RepositoryServiceProvider.webhook_url`.
        Events must be delivered via an HTTP POST request with a JSON payload.

        Returns the ID of the new webhook as returned by the provider, or None if the
        creation failed due to the repository not existing or the user not having permission
        to create a webhook.
        """
        raise NotImplementedError

    @abstractmethod
    def delete_webhook(self, repository_id: str, hook_id: str | None = None) -> bool:
        """
        Deletes a webhook from the specified repository.

        If `hook_id` is specified, the webhook with that ID must be deleted.
        Otherwise, all webhooks with URLs for which `is_valid_webhook` would return
        True should be deleted.

        Returns True if the deletion was successful, and False if it failed due to
        the repository not existing or the user not having permission to delete its
        webhooks.
        """
        raise NotImplementedError

    @abstractmethod
    def get_own_user(self) -> GenericUser | None:
        """
        Returns information about the user for which this class has been instantiated, or None if the user does not exist.

        For example, if the user ID is incorrectly specified.
        """
        raise NotImplementedError

    @abstractmethod
    def resolve_release_zipball_url(self, release_zipball_url: str) -> str | None:
        """TODO: why do we have this."""
        raise NotImplementedError

    @abstractmethod
    def fetch_release_zipball(
        self, release_zipball_url: str, timeout: int
    ) -> Generator[HTTPResponse]:
        """
        Returns the HTTP response for downloading the contents of a zipball from a given release.

        This is provider-specific functionality as it will require attaching an auth token
        to the request for private repos (and even public repos to avoid rate limits sometimes).
        """
        raise NotImplementedError

    @abstractmethod
    def retrieve_remote_file(
        self, repository_id: str, ref_name: str, file_name: str
    ) -> bytes | None:
        """
        Downloads the contents of a specific file in a repo for a given ref (which could be a tag, a commit ref, a branch name, etc).

        Returns the raw bytes, or None if the repo/file does not exist or the user doesn't have permission to view it.
        """
        raise NotImplementedError

    @abstractmethod
    def revoke_token(self, access_token: str):
        """Revoke the validity of a specific access token permanently."""
        raise NotImplementedError
