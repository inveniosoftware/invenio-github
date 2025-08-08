from copy import deepcopy
from dataclasses import asdict

from invenio_db import db
from invenio_i18n import gettext as _
from werkzeug.utils import cached_property

from invenio_github.errors import (
    RemoteAccountDataNotSet,
    RepositoryAccessError,
    RepositoryNotFoundError,
)
from invenio_github.models import Release, ReleaseStatus, Repository
from invenio_github.providers import GenericRelease, get_provider_by_id


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
                    release_instance = self.provider.get_repo_latest_release(
                        db_repo.provider_id
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

        return release_object.to_generic()

    def list_repo_releases(self, repo):
        # Retrieve releases and sort them by creation date
        release_instances = []
        for release_object in repo.releases.order_by(Release.created):
            release_instances.append(release_object.to_generic())
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
                str(repo.github_id)
            )
            if user_has_remote_access:
                return True

        raise RepositoryAccessError(
            user=self.provider.user_id, repo=repo.name, repo_id=repo.provider_id
        )
