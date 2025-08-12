from copy import deepcopy

from flask import current_app
from invenio_db import db
from invenio_i18n import gettext as _
from invenio_oauth2server.models import Token as ProviderToken
from sqlalchemy.exc import NoResultFound
from werkzeug.utils import cached_property

from invenio_vcs.errors import (
    RemoteAccountDataNotSet,
    RemoteAccountNotFound,
    RepositoryAccessError,
    RepositoryNotFoundError,
)
from invenio_vcs.models import Release, ReleaseStatus, Repository
from invenio_vcs.providers import get_provider_by_id
from invenio_vcs.proxies import current_vcs
from invenio_vcs.tasks import sync_hooks as sync_hooks_task
from invenio_vcs.utils import iso_utcnow


class VersionControlService:
    def __init__(self, provider: str, user_id: str) -> None:
        self.provider = get_provider_by_id(provider).for_user(user_id)

    @cached_property
    def is_authenticated(self):
        return self.provider.session_token is not None

    def list_repositories(self):
        """Retrieves user repositories, containing db repositories plus remote repositories."""
        vcs_repos = deepcopy(self.provider.user_available_repositories)
        if vcs_repos:
            # 'Enhance' our repos dict, from our database model
            db_repos = Repository.query.filter(
                Repository.provider_id.in_([int(k) for k in vcs_repos.keys()])
            )
            for db_repo in db_repos:
                if str(db_repo.provider_id) in vcs_repos:
                    release_instance = current_vcs.release_api_class(
                        db_repo.latest_release(), self.provider.factory.id
                    )
                    vcs_repos[str(db_repo.github_id)]["instance"] = db_repo
                    vcs_repos[str(db_repo.github_id)]["latest"] = release_instance

        return vcs_repos

    def get_repo_latest_release(self, repo):
        """Retrieves the repository last release."""
        # Bail out fast if object (Repository) not in DB session.
        if repo not in db.session:
            return None

        q = repo.releases.filter_by(status=ReleaseStatus.PUBLISHED)
        release_object = q.order_by(db.desc(Release.created)).first()

        return current_vcs.release_api_class(release_object, self.provider.factory.id)

    def list_repo_releases(self, repo):
        # Retrieve releases and sort them by creation date
        release_instances = []
        for release_object in repo.releases.order_by(Release.created):
            release_instances.append(
                current_vcs.release_api_class(release_object, self.provider.factory.id)
            )
        return release_instances

    def get_repo_default_branch(self, repo_id):
        return (
            self.provider.remote_account.extra_data.get("repos", {})
            .get(repo_id, None)
            .get("default_branch", None)
        )

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

    def get_repository(self, repo_id):
        """Retrieves one repository.

        Checks for access permission.
        """
        repo = Repository.get(provider_id=repo_id)
        if not repo:
            raise RepositoryNotFoundError(repo_id)

        # Might raise a RepositoryAccessError
        self.check_repo_access_permissions(repo)

        return repo

    def check_repo_access_permissions(self, repo):
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
            user_has_remote_access = self.provider.user_available_repositories.get(
                repo.provider_id
            )
            if user_has_remote_access:
                return True

        raise RepositoryAccessError(
            user=self.provider.user_id, repo=repo.name, repo_id=repo.provider_id
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

        if hooks:
            self._sync_hooks(vcs_repos.keys(), asynchronous=async_hooks)

        # Update changed names for repositories stored in DB
        db_repos = Repository.query.filter(
            Repository.user_id == self.provider.user_id,
        )

        for repo in db_repos:
            vcs_repo = vcs_repos.get(repo.github_id)
            if vcs_repo and repo.name != vcs_repo.full_name:
                repo.name = vcs_repo.full_name
                db.session.add(repo)

        # Remove ownership from repositories that the user has no longer
        # 'admin' permissions, or have been deleted.
        Repository.query.filter(
            Repository.user_id == self.provider.user_id,
            ~Repository.provider_id.in_(vcs_repos.keys()),
        ).update({"user_id": None, "hook": None}, synchronize_session=False)

        # Update repos and last sync
        self.provider.remote_account.extra_data.update(
            dict(
                repos=vcs_repos,
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
                self.provider.factory.id, self.provider.user_id, repo_ids
            )

    def sync_repo_hook(self, repo_id):
        """Sync a GitHub repo's hook with the locally stored repo."""
        # Get the hook that we may have set in the past
        hook = self.provider.get_first_valid_webhook(repo_id)
        vcs_repo = self.provider.get_repository(repo_id)

        # If hook on GitHub exists, get or create corresponding db object and
        # enable the hook. Otherwise remove the old hook information.
        repo = Repository.get(repo_id)

        if hook:
            if not repo:
                repo = Repository.create(
                    self.provider.user_id,
                    self.provider.factory.id,
                    repo_id,
                    vcs_repo.full_name,
                )
            if not repo.enabled:
                self.mark_repo_enabled(repo, hook.id)
        else:
            if repo:
                self.mark_repo_disabled(repo)

    def mark_repo_disabled(self, repo):
        """Disables an user repository."""
        repo.hook = None
        repo.user_id = None

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
            login=user.login,
            name=user.name,
            tokens=dict(
                webhook=hook_token.id,
            ),
            repos=dict(),
            last_sync=iso_utcnow(),
        )

        db.session.add(self.provider.remote_account)

    def enable_repository(self, repository_id):
        repos = self.provider.remote_account.extra_data.get("repos", {})
        if repository_id not in repos:
            raise RepositoryNotFoundError(
                repository_id, _("Failed to enable repository.")
            )

        return self.provider.create_webhook(repository_id)

    def disable_repository(self, repository_id):
        repos = self.provider.remote_account.extra_data.get("repos", {})
        if repository_id not in repos:
            raise RepositoryNotFoundError(
                repository_id, _("Failed to disable repository.")
            )

        remove_success = False
        if repos:
            remove_success = self.provider.delete_webhook(repository_id)

        return remove_success
