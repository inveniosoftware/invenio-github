from abc import abstractmethod
from contextlib import contextmanager
from dataclasses import asdict
from typing import TYPE_CHECKING

from flask import current_app
from invenio_access.permissions import authenticated_user
from invenio_access.utils import get_identity
from invenio_db import db
from invenio_i18n import gettext as _
from invenio_oauth2server.models import Token as ProviderToken
from sqlalchemy.exc import NoResultFound
from werkzeug.utils import cached_property

from invenio_vcs.config import get_provider_by_id
from invenio_vcs.errors import (
    RemoteAccountDataNotSet,
    RemoteAccountNotFound,
    RepositoryAccessError,
    RepositoryDisabledError,
    RepositoryNotFoundError,
    UserInfoNoneError,
)
from invenio_vcs.generic_models import GenericRelease, GenericRepository
from invenio_vcs.models import Release, ReleaseStatus, Repository
from invenio_vcs.proxies import current_vcs
from invenio_vcs.tasks import sync_hooks as sync_hooks_task
from invenio_vcs.utils import iso_utcnow

if TYPE_CHECKING:
    from invenio_vcs.providers import (
        RepositoryServiceProvider,
    )


class VCSService:
    def __init__(self, provider: "RepositoryServiceProvider") -> None:
        self.provider = provider

    @staticmethod
    def for_provider_and_user(provider_id: str, user_id: int):
        return VCSService(get_provider_by_id(provider_id).for_user(user_id))

    @staticmethod
    def for_provider_and_token(provider_id: str, user_id: int, access_token: str):
        return VCSService(
            get_provider_by_id(provider_id).for_access_token(user_id, access_token)
        )

    @cached_property
    def is_authenticated(self):
        return self.provider.session_token is not None

    @property
    def user_available_repositories(self):
        """Retrieve user repositories from user's remote data."""
        return Repository.query.filter(
            Repository.user_id == self.provider.user_id,
            Repository.provider == self.provider.factory.id,
        )

    @property
    def user_enabled_repositories(self):
        """Retrieve user repositories from the model."""
        return Repository.query.filter(
            Repository.user_id == self.provider.user_id,
            Repository.provider == self.provider.factory.id,
            Repository.hook != None,
        )

    def list_repositories(self):
        """Retrieves user repositories, containing db repositories plus remote repositories."""
        repos = {}
        for db_repo in self.user_available_repositories:
            repos[db_repo.provider_id] = asdict(GenericRepository.from_model(db_repo))
            release_instance = current_vcs.release_api_class(
                db_repo.latest_release(), self.provider
            )
            repos[db_repo.provider_id]["instance"] = db_repo
            repos[db_repo.provider_id]["latest"] = release_instance

        return repos

    def get_repo_latest_release(self, repo):
        """Retrieves the repository last release."""
        # Bail out fast if object (Repository) not in DB session.
        if repo not in db.session:
            return None

        q = repo.releases.filter_by(status=ReleaseStatus.PUBLISHED)
        release_object = q.order_by(db.desc(Release.created)).first()

        return current_vcs.release_api_class(release_object, self.provider)

    def list_repo_releases(self, repo):
        # Retrieve releases and sort them by creation date
        release_instances = []
        for release_object in repo.releases.order_by(Release.created):
            release_instances.append(
                current_vcs.release_api_class(release_object, self.provider)
            )
        return release_instances

    def get_repo_default_branch(self, repo_id):
        db_repo = self.user_available_repositories.filter(
            Repository.provider_id == repo_id
        ).first()

        if db_repo is None:
            return None

        return db_repo.default_branch

    def get_last_sync_time(self):
        """Retrieves the last sync delta time from github's client extra data.

        Time is computed as the delta between now and the last sync time.
        """
        extra_data = self.provider.remote_account.extra_data
        if not extra_data.get("last_sync"):
            raise RemoteAccountDataNotSet(
                self.provider.user_id,
                _("Last sync data is not set for user (remote data)."),
            )

        return extra_data["last_sync"]

    def get_repository(self, repo_id=None, repo_name=None):
        """Retrieves one repository.

        Checks for access permission.
        """
        repo = Repository.get(
            self.provider.factory.id, provider_id=repo_id, full_name=repo_name
        )
        if not repo:
            raise RepositoryNotFoundError(repo_id)

        # Might raise a RepositoryAccessError
        self.check_repo_access_permissions(repo)

        return repo

    def check_repo_access_permissions(self, repo: Repository):
        """Checks permissions from user on repo.

        Repo has access if any of the following is True:

        - user is the owner of the repo
        - user has access to the repo in GitHub (stored in RemoteAccount.extra_data.repos)
        """
        if self.provider.user_id and repo and repo.user_id:
            user_is_owner = repo.user_id == int(self.provider.user_id)
            if user_is_owner:
                return True

        if self.provider.remote_account and self.provider.remote_account.extra_data:
            user_has_remote_access_count = self.user_available_repositories.filter(
                Repository.provider_id == repo.provider_id
            ).count()
            if user_has_remote_access_count == 1:
                return True

        raise RepositoryAccessError(
            user=self.provider.user_id, repo=repo.full_name, repo_id=repo.provider_id
        )

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
        vcs_repos = self.provider.list_repositories()
        if vcs_repos is None:
            vcs_repos = {}

        if hooks:
            self._sync_hooks(vcs_repos.keys(), asynchronous=async_hooks)

        # Update changed names for repositories stored in DB
        db_repos = Repository.query.filter(
            Repository.user_id == self.provider.user_id,
            Repository.provider == self.provider.factory.id,
        ).all()

        for db_repo in db_repos:
            vcs_repo = vcs_repos.get(db_repo.provider_id)
            if not vcs_repo:
                continue

            changed = vcs_repo.to_model(db_repo)
            if changed:
                db.session.add(db_repo)

        # Remove ownership from repositories that the user has no longer
        # 'admin' permissions, or have been deleted.
        Repository.query.filter(
            Repository.user_id == self.provider.user_id,
            Repository.provider == self.provider.factory.id,
            ~Repository.provider_id.in_(vcs_repos.keys()),
        ).update({"user_id": None, "hook": None}, synchronize_session=False)

        # Add new repos from VCS to the DB (without the hook activated)
        for _, vcs_repo in vcs_repos.items():
            if any(r.provider_id == vcs_repo.id for r in db_repos):
                # We have already added this to our DB
                continue

            Repository.create(
                user_id=self.provider.user_id,
                provider=self.provider.factory.id,
                provider_id=vcs_repo.id,
                html_url=vcs_repo.html_url,
                default_branch=vcs_repo.default_branch,
                full_name=vcs_repo.full_name,
                description=vcs_repo.description,
                license_spdx=vcs_repo.license_spdx,
            )

        # Update last sync
        self.provider.remote_account.extra_data.update(
            dict(
                last_sync=iso_utcnow(),
            )
        )
        self.provider.remote_account.extra_data.changed()
        db.session.add(self.provider.remote_account)

    def _sync_hooks(self, repo_ids, asynchronous=True):
        """Check if a hooks sync task needs to be started."""
        if not asynchronous:
            for repo_id in repo_ids:
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
            sync_hooks_task.delay(
                self.provider.factory.id, self.provider.user_id, list(repo_ids)
            )

    def sync_repo_hook(self, repo_id):
        """Sync a GitHub repo's hook with the locally stored repo."""
        # Get the hook that we may have set in the past
        hook = self.provider.get_first_valid_webhook(repo_id)
        vcs_repo = self.provider.get_repository(repo_id)
        assert vcs_repo is not None

        # If hook on GitHub exists, get or create corresponding db object and
        # enable the hook. Otherwise remove the old hook information.
        db_repo = Repository.get(self.provider.factory.id, provider_id=repo_id)

        if hook:
            if not db_repo:
                db_repo = Repository.create(
                    user_id=self.provider.user_id,
                    provider=self.provider.factory.id,
                    provider_id=repo_id,
                    html_url=vcs_repo.html_url,
                    default_branch=vcs_repo.default_branch,
                    full_name=vcs_repo.full_name,
                    description=vcs_repo.description,
                    license_spdx=vcs_repo.license_spdx,
                )
            if not db_repo.enabled:
                self.mark_repo_enabled(db_repo, hook.id)
        else:
            if db_repo:
                self.mark_repo_disabled(db_repo)

    def mark_repo_disabled(self, repo):
        """Disables an user repository."""
        repo.hook = None

    def mark_repo_enabled(self, repo, hook):
        """Enables an user repository."""
        repo.hook = hook
        repo.user_id = self.provider.user_id

    def init_account(self):
        """Setup a new GitHub account."""
        if not self.provider.remote_account:
            raise RemoteAccountNotFound(
                self.provider.user_id, _("Remote account was not found for user.")
            )

        user = self.provider.get_own_user()
        if user is None:
            raise UserInfoNoneError

        # Setup local access tokens to be used by the webhooks
        hook_token = ProviderToken.create_personal(
            f"{self.provider.factory.id}-webhook",
            self.provider.user_id,
            scopes=["webhooks:event"],
            is_internal=True,
        )
        # Initial structure of extra data
        self.provider.remote_account.extra_data = dict(
            id=user.id,
            login=user.username,
            name=user.display_name,
            tokens=dict(
                webhook=hook_token.id,
            ),
            last_sync=iso_utcnow(),
        )

        db.session.add(self.provider.remote_account)

    def enable_repository(self, repository_id):
        db_repo = self.user_available_repositories.filter(
            Repository.provider_id == repository_id
        ).first()
        if db_repo is None:
            raise RepositoryNotFoundError(
                repository_id, _("Failed to enable repository.")
            )

        hook_id = self.provider.create_webhook(repository_id)
        if hook_id is None:
            return False

        self.mark_repo_enabled(db_repo, hook_id)
        return True

    def disable_repository(self, repository_id, hook_id=None):
        db_repo = self.user_available_repositories.filter(
            Repository.provider_id == repository_id
        ).first()

        if db_repo is None:
            raise RepositoryNotFoundError(
                repository_id, _("Failed to disable repository.")
            )

        if not db_repo.enabled:
            raise RepositoryDisabledError(repository_id)

        if not self.provider.delete_webhook(repository_id, hook_id):
            return False

        self.mark_repo_disabled(db_repo)
        return True


class VCSRelease:
    """A GitHub release."""

    def __init__(self, release: Release, provider: "RepositoryServiceProvider"):
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
    def _generic_release_and_repo(self):
        return self.provider.factory.webhook_event_to_generic(self.payload)

    @cached_property
    def generic_release(self) -> "GenericRelease":
        """Return release metadata."""
        return self._generic_release_and_repo[0]

    @cached_property
    def generic_repo(self) -> "GenericRepository":
        """Return repo metadata."""
        return self._generic_release_and_repo[1]

    @cached_property
    def db_repo(self) -> Repository:
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
        tag_name = self.generic_release.tag_name
        repo_name = self.generic_repo.full_name
        filename = f"{repo_name}-{tag_name}.zip"
        return filename

    @cached_property
    def release_zipball_url(self):
        """Returns the release zipball URL."""
        return self.generic_release.zipball_url

    @cached_property
    def user_identity(self):
        """Generates release owner's user identity."""
        identity = get_identity(self.db_repo.user)
        identity.provides.add(authenticated_user)
        identity.user = self.db_repo.user
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
            self.db_repo.provider_id, max=max_contributors
        )

    @cached_property
    def owner(self):
        """Get owner of repository as a creator."""
        try:
            return self.provider.get_repository_owner(self.db_repo.provider_id)
        except Exception:
            return None

    # Helper functions

    def is_first_release(self):
        """Checks whether the current release is the first release of the repository."""
        latest_release = self.db_repo.latest_release(ReleaseStatus.PUBLISHED)
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
        url = self.provider.resolve_release_zipball_url(url)

        if cache:
            self._resolved_zipball_url = url

        return url

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

    @contextmanager
    def fetch_zipball_file(self):
        """Fetch release zipball file using the current github session."""
        timeout = current_app.config.get("VCS_ZIPBALL_TIMEOUT", 300)
        zipball_url = self.resolve_zipball_url()
        return self.provider.fetch_release_zipball(zipball_url, timeout)

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
