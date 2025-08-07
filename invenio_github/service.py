from copy import deepcopy

from invenio_i18n import gettext as _
from werkzeug.utils import cached_property

from invenio_github.errors import RemoteAccountDataNotSet
from invenio_github.models import Repository
from invenio_github.providers import get_provider_by_id
from invenio_github.proxies import current_vcs


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
                        db_repo.latest_release()
                    )
                    vcs_repos[str(db_repo.github_id)]["instance"] = db_repo
                    vcs_repos[str(db_repo.github_id)]["latest"] = release_instance
        return vcs_repos

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
