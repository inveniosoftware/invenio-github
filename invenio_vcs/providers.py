from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from flask import current_app
from invenio_access.permissions import authenticated_user
from invenio_access.utils import get_identity
from invenio_i18n import gettext as _
from invenio_oauth2server.models import Token as ProviderToken
from invenio_oauthclient import current_oauthclient
from invenio_oauthclient.handlers import token_getter
from invenio_oauthclient.models import RemoteAccount, RemoteToken
from werkzeug.local import LocalProxy
from werkzeug.utils import cached_property

from invenio_vcs.errors import RemoteAccountDataNotSet
from invenio_vcs.models import Repository


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


@dataclass
class GenericUser:
    id: str
    username: str
    display_name: str


@dataclass
class GenericContributor:
    id: str
    username: str
    display_name: str
    contributions_count: int


class RepositoryServiceProviderFactory(ABC):
    def __init__(
        self, provider: type["RepositoryServiceProvider"], webhook_receiver_url: str
    ):
        self.provider = provider
        self.webhook_receiver_url = webhook_receiver_url

    @property
    @abstractmethod
    def remote_config(self):
        raise NotImplementedError

    @cached_property
    def remote(self):
        return LocalProxy(lambda: current_oauthclient.oauth.remote_apps[self.id])

    @property
    @abstractmethod
    def id(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def repository_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def repository_name_plural(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def icon(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def config(self) -> dict:
        raise NotImplementedError

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
        raise NotImplementedError

    @abstractmethod
    def list_repository_webhooks(self, repository_id):
        raise NotImplementedError

    def get_first_valid_webhook(self, repository_id):
        webhooks = self.list_repository_webhooks(repository_id)
        for hook in webhooks:
            if self.is_valid_webhook(hook.url):
                return hook
        return None

    @abstractmethod
    def get_repository(self, repository_id):
        raise NotImplementedError

    @abstractmethod
    def list_repository_contributors(self, repository_id, max):
        raise NotImplementedError

    @abstractmethod
    def get_repository_owner(self, repository_id):
        raise NotImplementedError

    @abstractmethod
    def create_webhook(self, repository_id):
        raise NotImplementedError

    @abstractmethod
    def delete_webhook(self, repository_id):
        raise NotImplementedError

    @abstractmethod
    def get_own_user(self):
        raise NotImplementedError


def get_provider_list() -> list[RepositoryServiceProviderFactory]:
    return current_app.config["VCS_PROVIDERS"]


def get_provider_by_id(id: str) -> RepositoryServiceProviderFactory:
    providers = get_provider_list()
    for provider in providers:
        if id == provider.id:
            return provider
    raise Exception(f"VCS provider with ID {id} not registered")


class VCSRelease:
    """A GitHub release."""

    def __init__(self, release, provider: RepositoryServiceProvider):
        """Constructor."""
        self.db_release = release
        self.provider = provider
        self._resolved_zipball_url = None

    @cached_property
    def record(self):
        """Release record."""
        return self.resolve_record()

    @cached_property
    def event(self):
        """Get release event."""
        return self.db_release.event

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
        if self.db_release.repository_id:
            repository = self.db_release.repository
        else:
            repository = Repository.query.filter_by(
                user_id=self.event.user_id, provider_id=self.provider.factory.id
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
        """Returns the release zipball URL."""
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
        max_contributors = current_app.config.get("VCS_MAX_CONTRIBUTORS_NUMBER", 30)
        return self.provider.list_repository_contributors(
            self.repository_object.id, max=max_contributors
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
        """Test if the zipball URL is accessible and return the resolved URL."""
        return self.resolve_zipball_url()

    def resolve_zipball_url(self, cache=True):
        """Resolve the zipball URL.

        This method will try to resolve the zipball URL by making a HEAD request,
        handling the following edge cases:

        - In the case of a 300 Multiple Choices response, which can happen when a tag
          and branch have the same name, it will try to fetch an "alternate" link.
        - If the access token does not have the required scopes/permissions to access
          public links, it will fallback to a non-authenticated request.
        """
        if self._resolved_zipball_url and cache:
            return self._resolved_zipball_url

        url = self.release_zipball_url

        # Execute a HEAD request to the zipball url to test if it is accessible.
        response = self.gh.api.session.head(url, allow_redirects=True)

        # In case where there is a tag and branch with the same name, we might get back
        # a "300 Multiple Choices" response, which requires fetching an "alternate"
        # link.
        if response.status_code == 300:
            alternate_url = response.links.get("alternate", {}).get("url")
            if alternate_url:
                url = alternate_url  # Use the alternate URL
                response = self.gh.api.session.head(url, allow_redirects=True)

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

        if cache:
            self._resolved_zipball_url = response.url

        return response.url

    # High level API

    def release_failed(self):
        """Set release status to FAILED."""
        self.db_release.status = ReleaseStatus.FAILED

    def release_processing(self):
        """Set release status to PROCESSING."""
        self.db_release.status = ReleaseStatus.PROCESSING

    def release_published(self):
        """Set release status to PUBLISHED."""
        self.db_release.status = ReleaseStatus.PUBLISHED

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
        zipball_url = self.resolve_zipball_url()
        with session.get(zipball_url, stream=True, timeout=timeout) as resp:
            yield resp.raw

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
