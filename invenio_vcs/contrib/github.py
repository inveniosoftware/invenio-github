from collections import defaultdict

import github3
from github3.repos import ShortRepository
from invenio_oauthclient.contrib.github import GitHubOAuthSettingsHelper
from werkzeug.utils import cached_property

from invenio_github.oauth.handlers import account_setup_handler, disconnect_handler
from invenio_github.providers import (
    GenericRelease,
    GenericRepository,
    GenericWebhook,
    RepositoryServiceProvider,
    RepositoryServiceProviderFactory,
)


class GitHubProviderFactory(RepositoryServiceProviderFactory):
    def __init__(
        self,
        webhook_receiver_url,
        id="github",
        name="GitHub",
        config={},
    ):
        super().__init__(GitHubProvider, webhook_receiver_url)
        self._id = id
        self._name = name
        self._config = defaultdict(
            config,
            base_url="https://github.com",
            credentials_key="GITHUB_APP_CREDENTIALS",
            shared_secret="",
            insecure_ssl=False,
        )

    @property
    def remote_config(self):
        request_token_params = {
            "scope": "read:user,user:email,admin:repo_hook,read:org"
        }

        helper = GitHubOAuthSettingsHelper(
            base_url=self.base_url, app_key=self.credentials_key
        )
        github_app = helper.remote_app
        github_app["disconnect_handler"] = disconnect_handler
        github_app["signup_handler"]["setup"] = account_setup_handler
        github_app["params"]["request_token_params"] = request_token_params

        return github_app

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def repository_name(self):
        return "repository"

    @property
    def repository_name_plural(self):
        return "repositories"

    @property
    def icon(self):
        return "github"

    @property
    def config(self):
        return self._config


class GitHubProvider(RepositoryServiceProvider):
    @cached_property
    def _gh(self):
        return github3.login(token=self.access_token(self.user_id))

    def list_repositories(self):
        if self._gh is None:
            return None

        repos: dict[str, GenericRepository] = {}
        for repo in self._gh.repositories():
            assert isinstance(repo, ShortRepository)

            if repo.permissions["admin"]:
                repos[str(repo.id)] = GenericRepository(
                    str(repo.id),
                    repo.full_name,
                    repo.description,
                    repo.default_branch,
                )

        return repos

    def list_repository_webhooks(self, repository_id):
        assert repository_id.isdigit()
        if self._gh is None:
            return None
        repo = self._gh.repository_with_id(int(repository_id))
        if repo is None:
            return None

        hooks = []
        for hook in repo.hooks():
            hooks.append(
                GenericWebhook(str(hook.id), repository_id, hook.config.get("url", ""))
            )
        return hooks

    def get_repository(self, repository_id):
        assert repository_id.isdigit()
        if self._gh is None:
            return None

        repo = self._gh.repository_with_id(int(repository_id))
        if repo is None:
            return None

        return GenericRepository(
            str(repo.id), repo.full_name, repo.description, repo.default_branch
        )

    def get_repo_latest_release(self, repository_id):
        assert repository_id.isdigit()
        if self._gh is None:
            return None
        repo = self._gh.repository_with_id(int(repository_id))
        if repo is None:
            return None

        release = repo.latest_release()
        if not release:
            return None

        return GenericRelease(
            str(release.id),
            release.name,
            release.tag_name,
            release.tarball_url,
            release.zipball_url,
            release.created_at,
        )

    def create_webhook(self, repository_id, url):
        assert repository_id.isdigit()
        if self._gh is None:
            return None

        hook_config = dict(
            url=url,
            content_type="json",
            secret=self.factory.config["shared_secret"],
            insecure_ssl="1" if self.factory.config["insecure_ssl"] else "0",
        )

        repo = self._gh.repository_with_id(int(repository_id))
        if repo is None:
            return False

        hooks = (h for h in repo.hooks() if h.config.get("url", "") == url)
        hook = next(hooks, None)

        if not hook:
            hook = repo.create_hook("web", hook_config, events=["release"])
        else:
            hook.edit(config=hook_config, events=["release"])

        return True

    def delete_webhook(self, repository_id):
        assert repository_id.isdigit()
        if self._gh is None:
            return None

        repo = self._gh.repository_with_id(int(repository_id))
        if repo is None:
            return False

        hooks = (
            h for h in repo.hooks() if self.is_valid_webhook(h.config.get("url", ""))
        )
        hook = next(hooks, None)
        if not hook or hook.delete():
            return True
        return False
