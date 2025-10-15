# -*- coding: utf-8 -*-
#
# Copyright (C) 2025 CERN.
#
# Invenio-VCS is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
#
# Some of the code in this file was taken from https://codebase.helmholtz.cloud/rodare/invenio-gitlab
# and relicensed under MIT with permission from the authors.
"""Fixture test impl for GitLab."""

from typing import Any, Iterator
from unittest.mock import MagicMock, patch

import gitlab.const
import gitlab.v4.objects

from invenio_vcs.contrib.gitlab import GitLabProviderFactory
from invenio_vcs.generic_models import (
    GenericContributor,
    GenericOwner,
    GenericRelease,
    GenericRepository,
    GenericUser,
    GenericWebhook,
)
from invenio_vcs.providers import (
    RepositoryServiceProvider,
    RepositoryServiceProviderFactory,
)
from tests.contrib_fixtures.patcher import TestProviderPatcher


def gitlab_namespace_metadata(id: int):
    """Namespace metadata generator."""
    return {
        "id": id,
        "name": "Diaspora",
        "path": "diaspora",
        "kind": "group",
        "full_path": "diaspora",
        "parent_id": None,
        "avatar_url": None,
        "web_url": "https://gitlab.example.com/diaspora",
    }


def gitlab_project_metadata(
    id: int, full_name: str, default_branch: str, description: str | None
):
    """Project metadata generator."""
    return {
        "id": id,
        "description": description,
        "name": "Diaspora Client",
        "name_with_namespace": "Diaspora / Diaspora Client",
        "path": "diaspora-client",
        "path_with_namespace": full_name,
        "created_at": "2013-09-30T13:46:02Z",
        "default_branch": default_branch,
        "tag_list": ["example", "disapora client"],
        "topics": ["example", "disapora client"],
        "ssh_url_to_repo": "git@gitlab.example.com:%s.git" % full_name,
        "http_url_to_repo": "https://gitlab.example.com/%s.git" % full_name,
        "web_url": "https://gitlab.example.com/%s" % full_name,
        "avatar_url": "https://gitlab.example.com/uploads/project/avatar/%d/uploads/avatar.png"
        % id,
        "star_count": 0,
        "last_activity_at": "2013-09-30T13:46:02Z",
        "visibility": "public",
        "namespace": gitlab_namespace_metadata(1),
    }


def gitlab_contributor_metadata(
    email: str, contribution_count: int | None, name: str | None = "Example"
):
    """Contributor metadata generator."""
    return {
        "name": name,
        "email": email,
        "commits": contribution_count,
        "additions": 0,
        "deletions": 0,
    }


def gitlab_user_metadata(id: int, username: str, name: str | None):
    """User metadata generator."""
    return {
        "id": id,
        "username": username,
        "name": name,
        "state": "active",
        "locked": False,
        "avatar_url": "https://gitlab.example.com/uploads/user/avatar/%d/cd8.jpeg" % id,
        "web_url": "https://gitlab.example.com/%s" % username,
    }


def gitlab_webhook_metadata(
    id: int,
    project_id: int,
    url: str,
):
    """Webhook metadata generator."""
    return {
        "id": id,
        "url": url,
        "name": "Hook name",
        "description": "Hook description",
        "project_id": project_id,
        "push_events": True,
        "push_events_branch_filter": "",
        "issues_events": True,
        "confidential_issues_events": True,
        "merge_requests_events": True,
        "tag_push_events": True,
        "note_events": True,
        "confidential_note_events": True,
        "job_events": True,
        "pipeline_events": True,
        "wiki_page_events": True,
        "deployment_events": True,
        "releases_events": True,
        "milestone_events": True,
        "feature_flag_events": True,
        "enable_ssl_verification": True,
        "repository_update_events": True,
        "alert_status": "executable",
        "disabled_until": None,
        "url_variables": [],
        "created_at": "2012-10-12T17:04:47Z",
        "resource_access_token_events": True,
        "custom_webhook_template": '{"event":"{{object_kind}}"}',
        "custom_headers": [{"key": "Authorization"}],
    }


def gitlab_project_member_metadata(id: int, username: str, access_level: int):
    """Project member metadata generator."""
    return {
        "id": id,
        "username": username,
        "name": "Raymond Smith",
        "state": "active",
        "avatar_url": "https://www.gravatar.com/avatar/c2525a7f58ae3776070e44c106c48e15?s=80&d=identicon",
        "web_url": "http://192.168.1.8:3000/root",
        "created_at": "2012-09-22T14:13:35Z",
        "created_by": {
            "id": 2,
            "username": "john_doe",
            "name": "John Doe",
            "state": "active",
            "avatar_url": "https://www.gravatar.com/avatar/c2525a7f58ae3776070e44c106c48e15?s=80&d=identicon",
            "web_url": "http://192.168.1.8:3000/root",
        },
        "expires_at": "2012-10-22",
        "access_level": access_level,
        "group_saml_identity": None,
    }


def gitlab_webhook_payload(
    id: int,
    tag_name: str,
    release_name: str | None,
    release_description: str | None,
    project_id: int,
    project_full_name: str,
    project_default_branch: str,
    project_description: str | None,
):
    """Return a sample webhook payload."""
    return {
        "id": id,
        "created_at": "2020-11-02 12:55:12 UTC",
        "description": release_description,
        "name": release_name,
        "released_at": "2020-11-02 12:55:12 UTC",
        "tag": tag_name,
        "object_kind": "release",
        "project": gitlab_project_metadata(
            project_id, project_full_name, project_default_branch, project_description
        ),
        "url": "https://example.com/gitlab-org/release-webhook-example/-/releases/v1.1",
        "action": "create",
        "assets": {
            "count": 5,
            "links": [
                {
                    "id": 1,
                    "link_type": "other",
                    "name": "Changelog",
                    "url": "https://example.net/changelog",
                }
            ],
            "sources": [
                {
                    "format": "zip",
                    "url": "https://example.com/gitlab-org/release-webhook-example/-/archive/v1.1/release-webhook-example-v1.1.zip",
                },
                {
                    "format": "tar.gz",
                    "url": "https://example.com/gitlab-org/release-webhook-example/-/archive/v1.1/release-webhook-example-v1.1.tar.gz",
                },
                {
                    "format": "tar.bz2",
                    "url": "https://example.com/gitlab-org/release-webhook-example/-/archive/v1.1/release-webhook-example-v1.1.tar.bz2",
                },
                {
                    "format": "tar",
                    "url": "https://example.com/gitlab-org/release-webhook-example/-/archive/v1.1/release-webhook-example-v1.1.tar",
                },
            ],
        },
        "commit": {
            "id": "ee0a3fb31ac16e11b9dbb596ad16d4af654d08f8",
            "message": "Release v1.1",
            "title": "Release v1.1",
            "timestamp": "2020-10-31T14:58:32+11:00",
            "url": "https://example.com/gitlab-org/release-webhook-example/-/commit/ee0a3fb31ac16e11b9dbb596ad16d4af654d08f8",
            "author": {"name": "Example User", "email": "user@example.com"},
        },
    }


class GitLabPatcher(TestProviderPatcher):
    """Patch the GitLab API primitives to avoid real API calls and return test data instead."""

    @staticmethod
    def provider_factory() -> RepositoryServiceProviderFactory:
        """GitLab provider factory."""
        return GitLabProviderFactory(
            base_url="https://gitlab.com",
            webhook_receiver_url="http://localhost:5000/api/receivers/github/events/?access_token={token}",
        )

    @staticmethod
    def test_webhook_payload(
        generic_repository: GenericRepository,
        generic_release: GenericRelease,
        generic_repo_owner: GenericOwner,
    ) -> dict[str, Any]:
        """Return a sample webhook payload."""
        return gitlab_webhook_payload(
            int(generic_release.id),
            generic_release.tag_name,
            generic_release.name,
            generic_release.body,
            int(generic_repository.id),
            generic_repository.full_name,
            generic_repository.default_branch,
            generic_repository.description,
        )

    def patch(
        self,
        test_generic_repositories: list[GenericRepository],
        test_generic_contributors: list[GenericContributor],
        test_collaborators: list[dict[str, Any]],
        test_generic_webhooks: list[GenericWebhook],
        test_generic_user: GenericUser,
        test_file: dict[str, Any],
    ) -> Iterator[RepositoryServiceProvider]:
        """Configure the patch and yield within the patched context."""
        mock_gl = MagicMock()
        mock_gl.projects = MagicMock()
        mock_gl.users = MagicMock()
        mock_gl.namespaces = MagicMock()

        # We need contributors to correspond to users for the search operation.
        # But the list should also contain the main test user.
        test_user_email = "%s@inveniosoftware.org" % test_generic_user.username
        test_user = gitlab.v4.objects.User(
            mock_gl.users,
            gitlab_user_metadata(
                int(test_generic_user.id),
                test_generic_user.username,
                test_generic_user.display_name,
            ),
        )
        # The email isn't returned in the API response (see https://docs.gitlab.com/api/users/#as-a-regular-user)
        # so we store it separately here for querying.
        users: dict[str, gitlab.v4.objects.User] = {test_user_email: test_user}
        mock_gl.user = test_user

        project_members: list[gitlab.v4.objects.ProjectMemberAll] = []
        for collaborator in test_collaborators:
            project_members.append(
                gitlab.v4.objects.ProjectMemberAll(
                    mock_gl.projects,
                    gitlab_project_member_metadata(
                        int(collaborator["id"]),
                        collaborator["username"],
                        (
                            gitlab.const.MAINTAINER_ACCESS
                            if collaborator["admin"]
                            else gitlab.const.GUEST_ACCESS
                        ),
                    ),
                )
            )

        # Some lesser-used API routes return dicts instead of dedicated objects
        contributors: list[dict[str, Any]] = []
        for generic_contributor in test_generic_contributors:
            contributor_email = "%s@inveniosoftware.org" % generic_contributor.username
            contributors.append(
                gitlab_contributor_metadata(
                    contributor_email,
                    generic_contributor.contributions_count,
                    generic_contributor.display_name,
                )
            )
            users[contributor_email] = gitlab.v4.objects.User(
                mock_gl.users,
                gitlab_user_metadata(
                    int(generic_contributor.id),
                    generic_contributor.username,
                    generic_contributor.display_name,
                ),
            )

        def mock_users_list(search: str | None = None):
            if search is None:
                return users
            return [users[search]]

        mock_gl.users.list = MagicMock(side_effect=mock_users_list)

        # We need to globally override this property because the method is provided as a
        # property within a mixin which cannot be overriden on the instance level.
        Project = gitlab.v4.objects.Project
        Project.repository_contributors = MagicMock(return_value=contributors)

        projs: dict[int, gitlab.v4.objects.Project] = {}
        for generic_repo in test_generic_repositories:
            proj = Project(
                mock_gl.projects,
                gitlab_project_metadata(
                    int(generic_repo.id),
                    generic_repo.full_name,
                    generic_repo.default_branch,
                    generic_repo.description,
                ),
            )

            hooks: list[gitlab.v4.objects.ProjectHook] = []
            for hook in test_generic_webhooks:
                if hook.id != generic_repo.id:
                    continue

                hooks.append(
                    gitlab.v4.objects.ProjectHook(
                        mock_gl.projects,
                        gitlab_webhook_metadata(
                            int(hook.id), int(generic_repo.id), hook.url
                        ),
                    )
                )

            proj.hooks = MagicMock()
            proj.hooks.list = MagicMock(return_value=hooks)
            new_hook = MagicMock()
            new_hook.id = 12345
            proj.hooks.create = MagicMock(return_value=new_hook)
            proj.hooks.delete = MagicMock()

            proj.members_all = MagicMock()
            proj.members_all.list = MagicMock(return_value=project_members)

            def mock_get_file(file_path: str, ref: str):
                if file_path == test_file["path"]:
                    file = MagicMock()
                    file.decode = MagicMock(
                        return_value=test_file["content"].encode("ascii")
                    )
                    return file
                else:
                    raise gitlab.GitlabGetError()

            proj.files = MagicMock()
            proj.files.get = MagicMock(side_effect=mock_get_file)

            projs[int(generic_repo.id)] = proj

        def mock_projects_get(id: int, lazy=False):
            """We need to take the lazy param even though we ignore it."""
            return projs[id]

        mock_gl.projects.list = MagicMock(return_value=projs.values())
        mock_gl.projects.get = MagicMock(side_effect=mock_projects_get)

        with patch("invenio_vcs.contrib.gitlab.GitLabProvider._gl", new=mock_gl):
            yield self.provider
