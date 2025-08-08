from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from flask import current_app
from invenio_i18n import gettext as _
from invenio_oauth2server.models import Token as ProviderToken
from invenio_oauthclient import current_oauthclient
from invenio_oauthclient.handlers import token_getter
from invenio_oauthclient.models import RemoteAccount, RemoteToken
from werkzeug.local import LocalProxy
from werkzeug.utils import cached_property

from invenio_vcs.errors import RemoteAccountDataNotSet


@dataclass
class GenericWebhook:
    id: str
    repository_id: str
    url: str


@dataclass
class GenericRepository:
    id: str
    full_name: str
    description: str
    default_branch: str


@dataclass
class GenericRelease:
    id: str
    name: str
    tag_name: str
    tarball_url: str
    zipball_url: str
    created_at: datetime


class RepositoryServiceProviderFactory(ABC):
    def __init__(
        self, provider: type["RepositoryServiceProvider"], webhook_receiver_url: str
    ):
        self.provider = provider
        self.webhook_receiver_url = webhook_receiver_url

    @property
    @abstractmethod
    def remote_config(self):
        pass

    @cached_property
    def remote(self):
        return LocalProxy(lambda: current_oauthclient.oauth.remote_apps[self.id])

    @property
    @abstractmethod
    def id(self) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def repository_name(self) -> str:
        pass

    @property
    @abstractmethod
    def repository_name_plural(self) -> str:
        pass

    @property
    @abstractmethod
    def icon(self) -> str:
        pass

    @property
    @abstractmethod
    def config(self) -> dict:
        pass

    def for_user(self, user_id: str):
        return self.provider(self, user_id)


class RepositoryServiceProvider(ABC):
    def __init__(self, factory: RepositoryServiceProviderFactory, user_id: str) -> None:
        self.factory = factory
        self.user_id = user_id

    @cached_property
    def remote_account(self):
        """Return remote account."""
        return RemoteAccount.get(self.user_id, self.factory.remote.consumer_key)

    @cached_property
    def user_available_repositories(self):
        """Retrieve user repositories from user's remote data."""
        return self.remote_account.extra_data.get("repos", {})

    @cached_property
    def access_token(self):
        """Return OAuth access token's value."""
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

    def is_valid_webhook(self, url):
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
    def list_repositories(self):
        pass

    @abstractmethod
    def list_repository_webhooks(self, repository_id):
        pass

    @abstractmethod
    def get_repository(self, repository_id):
        pass

    @abstractmethod
    def get_repo_latest_release(self, repository_id):
        pass

    @abstractmethod
    def create_webhook(self, repository_id, url):
        pass

    @abstractmethod
    def delete_webhook(self, repository_id, webhook_id):
        pass


def get_provider_list() -> list[RepositoryServiceProviderFactory]:
    return current_app.config["VCS_PROVIDERS"]


def get_provider_by_id(id: str) -> RepositoryServiceProviderFactory:
    providers = get_provider_list()
    for provider in providers:
        if id == provider.id:
            return provider
    raise Exception(f"VCS provider with ID {id} not registered")
