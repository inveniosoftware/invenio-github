from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generator
from urllib.parse import urlparse

from invenio_i18n import gettext as _
from invenio_oauth2server.models import Token as ProviderToken
from invenio_oauthclient import current_oauthclient
from invenio_oauthclient.handlers import token_getter
from invenio_oauthclient.models import RemoteAccount, RemoteToken
from urllib3 import HTTPResponse
from werkzeug.local import LocalProxy
from werkzeug.utils import cached_property

from invenio_vcs.errors import RemoteAccountDataNotSet
from invenio_vcs.oauth.handlers import OAuthHandlers


class RepositoryServiceProviderFactory(ABC):
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
    ):
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

    @property
    @abstractmethod
    def remote_config(self):
        raise NotImplementedError

    @property
    def oauth_handlers(self):
        return OAuthHandlers(self)

    @cached_property
    def remote(self):
        return LocalProxy(lambda: current_oauthclient.oauth.remote_apps[self.id])

    @property
    @abstractmethod
    def config(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def url_for_tag(self, repository_name, tag_name) -> str:
        raise NotImplementedError

    @abstractmethod
    def url_for_new_release(self, repository_name) -> str:
        raise NotImplementedError

    @abstractmethod
    def url_for_new_file(self, repository_name, branch_name, file_name) -> str:
        raise NotImplementedError

    @abstractmethod
    def webhook_is_create_release_event(self, event_payload: dict[str, Any]):
        raise NotImplementedError

    @abstractmethod
    def webhook_event_to_generic(
        self, event_payload: dict[str, Any]
    ) -> tuple[GenericRelease, GenericRepository]:
        raise NotImplementedError

    def for_user(self, user_id: int):
        return self.provider(self, user_id)

    def for_access_token(self, user_id: int, access_token: str):
        return self.provider(self, user_id, access_token=access_token)

    @property
    def vocabulary(self):
        return {
            "id": self.id,
            "name": self.name,
            "repository_name": self.repository_name,
            "repository_name_plural": self.repository_name_plural,
            "icon": self.icon,
        }


class RepositoryServiceProvider(ABC):
    def __init__(
        self, factory: RepositoryServiceProviderFactory, user_id: int, access_token=None
    ) -> None:
        self.factory = factory
        self.user_id = user_id
        self._access_token = access_token

    @cached_property
    def remote_account(self):
        """Return remote account."""
        return RemoteAccount.get(self.user_id, self.factory.remote.consumer_key)

    @cached_property
    def access_token(self):
        """Return OAuth access token's value."""
        if self._access_token is not None:
            return self._access_token

        token = RemoteToken.get(self.user_id, self.factory.remote.consumer_key)
        if not token:
            # The token is not yet in DB, it is retrieved from the request session.
            return self.factory.remote.get_request_token()[0]
        return token.access_token

    @property
    def session_token(self):
        """Return OAuth session token."""
        session_token = token_getter(self.factory.remote)
        if session_token:
            token = RemoteToken.get(
                self.user_id,
                self.factory.remote.consumer_key,
                access_token=session_token[0],
            )
            return token
        return None

    @cached_property
    def webhook_url(self):
        """Return the url to be used by a GitHub webhook."""
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
        raise NotImplementedError

    @abstractmethod
    def list_repository_webhooks(
        self, repository_id: str
    ) -> list[GenericWebhook] | None:
        raise NotImplementedError

    def get_first_valid_webhook(self, repository_id: str) -> GenericWebhook | None:
        webhooks = self.list_repository_webhooks(repository_id)
        if webhooks is None:
            return None
        for hook in webhooks:
            if self.is_valid_webhook(hook.url):
                return hook
        return None

    @abstractmethod
    def get_repository(self, repository_id: str) -> GenericRepository | None:
        raise NotImplementedError

    @abstractmethod
    def list_repository_contributors(
        self, repository_id: str, max: int
    ) -> list[GenericContributor] | None:
        raise NotImplementedError

    @abstractmethod
    def get_repository_owner(self, repository_id: str) -> GenericOwner | None:
        raise NotImplementedError

    @abstractmethod
    def create_webhook(self, repository_id: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def delete_webhook(self, repository_id: str, hook_id: str | None = None) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_own_user(self) -> GenericUser | None:
        raise NotImplementedError

    @abstractmethod
    def resolve_release_zipball_url(self, release_zipball_url: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def fetch_release_zipball(
        self, release_zipball_url: str, timeout: int
    ) -> Generator[HTTPResponse]:
        raise NotImplementedError

    @abstractmethod
    def retrieve_remote_file(
        self, repository_id: str, tag_name: str, file_name: str
    ) -> bytes | None:
        raise NotImplementedError

    @abstractmethod
    def revoke_token(self, access_token: str):
        raise NotImplementedError
