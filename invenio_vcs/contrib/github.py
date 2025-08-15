import json
from datetime import datetime

import dateutil
import github3
import requests
from flask import current_app
from github3.repos import ShortRepository
from invenio_i18n import gettext as _
from invenio_oauthclient.contrib.github import GitHubOAuthSettingsHelper
from werkzeug.utils import cached_property

from invenio_vcs.errors import ReleaseZipballFetchError, UnexpectedProviderResponse
from invenio_vcs.providers import (
    GenericContributor,
    GenericRelease,
    GenericRepository,
    GenericUser,
    GenericWebhook,
    RepositoryServiceProvider,
    RepositoryServiceProviderFactory,
)


class GitHubProviderFactory(RepositoryServiceProviderFactory):
    def __init__(
        self,
        base_url,
        webhook_receiver_url,
        id="github",
        name="GitHub",
        config={},
    ):
        super().__init__(GitHubProvider, base_url, webhook_receiver_url)
        self._id = id
        self._name = name
        self._config = dict()
        self._config.update(
            credentials_key="GITHUB_APP_CREDENTIALS",
            shared_secret="",
            insecure_ssl=False,
        )
        self._config.update(config)

    @property
    def remote_config(self):
        request_token_params = {
            "scope": "read:user,user:email,admin:repo_hook,read:org"
        }

        helper = GitHubOAuthSettingsHelper(
            base_url=self.base_url, app_key=self.config["credentials_key"]
        )
        github_app = helper.remote_app
        github_app["disconnect_handler"] = self.oauth_handlers.disconnect_handler
        github_app["signup_handler"][
            "setup"
        ] = self.oauth_handlers.account_setup_handler
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

    def webhook_is_create_release_event(self, event_payload):
        action = event_payload.get("action")
        is_draft_release = event_payload.get("release", {}).get("draft")

        # Draft releases do not create releases on invenio
        is_create_release_event = (
            action in ("published", "released", "created") and not is_draft_release
        )
        return is_create_release_event

    def webhook_event_to_generic(self, event_payload):
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

        license_spdx = event_payload["repository"].get("license")
        if license_spdx is not None:
            license_spdx = filter_license_spdx(license_spdx["spdx_id"])

        repo = GenericRepository(
            id=str(event_payload["repository"]["id"]),
            full_name=event_payload["repository"]["full_name"],
            html_url=event_payload["repository"]["html_url"],
            description=event_payload["repository"].get("description"),
            default_branch=event_payload["repository"]["default_branch"],
            license_spdx=license_spdx,
        )

        return (release, repo)

    def url_for_tag(self, repository_name, tag_name):
        return "{}/{}/tree/{}".format(self.base_url, repository_name, tag_name)


class GitHubProvider(RepositoryServiceProvider):
    @cached_property
    def _gh(self):
        if self.factory.base_url == "https://github.com":
            return github3.login(token=self.access_token)
        else:
            return github3.enterprise_login(
                url=self.factory.base_url, token=self.access_token
            )

    @staticmethod
    def _extract_license(repo):
        # The GitHub API returns the `license` as a simple key of the ShortRepository.
        # But for some reason github3py does not include a mapping for this.
        # So the only way to access it without making an additional request is to convert
        # the repo to a dict.
        repo_dict = repo.as_dict()
        license_obj = repo_dict["license"]
        if license_obj is not None:
            spdx = license_obj["spdx_id"]
            if spdx == "NOASSERTION":
                # For 'other' type of licenses, Github sets the spdx_id to NOASSERTION
                return None
            return spdx
        return None

    def list_repositories(self):
        if self._gh is None:
            return None

        repos: dict[str, GenericRepository] = {}
        for repo in self._gh.repositories():
            assert isinstance(repo, ShortRepository)

            if repo.permissions["admin"]:
                repos[str(repo.id)] = GenericRepository(
                    id=str(repo.id),
                    full_name=repo.full_name,
                    description=repo.description,
                    html_url=repo.html_url,
                    default_branch=repo.default_branch,
                    license_spdx=GitHubProvider._extract_license(repo),
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
                GenericWebhook(
                    id=str(hook.id),
                    repository_id=repository_id,
                    url=hook.config.get("url"),
                )
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
            id=str(repo.id),
            full_name=repo.full_name,
            description=repo.description,
            html_url=repo.html_url,
            default_branch=repo.default_branch,
            license_spdx=GitHubProvider._extract_license(repo),
        )

    def create_webhook(self, repository_id):
        assert repository_id.isdigit()
        if self._gh is None:
            return None

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
        assert repository_id.isdigit()
        if self._gh is None:
            return False

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
        if self._gh is None:
            return None

        user = self._gh.me()
        if user is not None:
            return GenericUser(user.id, user.login, user.name)

        return None

    def list_repository_contributors(self, repository_id, max):
        assert repository_id.isdigit()
        if self._gh is None:
            return None

        repo = self._gh.repository_with_id(repository_id)
        if repo is None:
            return None

        contributors_iter = repo.contributors(number=max)
        # Consume the iterator to materialize the request and have a `last_status``.
        contributors = list(contributors_iter)
        status = contributors_iter.last_status
        if status == 200:
            # Sort by contributions and filter only users.
            sorted_contributors = sorted(
                (c for c in contributors if c.type == "User"),
                key=lambda x: x.contributions_count,
                reverse=True,
            )

            contributors = []
            for c in sorted_contributors:
                contributions_count = c.contributions_count
                c = c.refresh()
                contributors.append(
                    GenericContributor(
                        id=c.id,
                        username=c.login,
                        display_name=c.name,
                        contributions_count=contributions_count,
                        company=c.company,
                    )
                )

            return contributors
        else:
            raise UnexpectedProviderResponse(
                _(
                    "Provider returned unexpected code: %(status)s for release in repo %(repo_id)s"
                )
                % {"status": status, "repo_id": repository_id}
            )

    def get_repository_owner(self, repository_id):
        assert repository_id.isdigit()
        if self._gh is None:
            return None

        repo = self._gh.repository_with_id(repository_id)
        if repo is None:
            return None

        return GenericUser(
            id=repo.owner.id,
            username=repo.owner.login,
            display_name=repo.owner.full_name,
        )

    def resolve_release_zipball_url(self, release_zipball_url):
        if self._gh is None:
            return None

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
        with self._gh.session.get(
            release_zipball_url, stream=True, timeout=timeout
        ) as resp:
            yield resp.raw

    def retrieve_remote_file(self, repository_id, tag_name, file_name):
        assert repository_id.isdigit()
        if self._gh is None:
            return None

        try:
            return self._gh.repository_with_id(repository_id).file_contents(
                path=file_name, ref=tag_name
            )
        except github3.exceptions.NotFoundError:
            return None

    def revoke_token(self, access_token):
        client_id, client_secret = self._gh.session.retrieve_client_credentials()
        url = self._gh._build_url("applications", str(client_id), "token")
        with self._gh.session.temporary_basic_auth(client_id, client_secret):
            response = self._gh._delete(
                url, data=json.dumps({"access_token": access_token})
            )
        return response
