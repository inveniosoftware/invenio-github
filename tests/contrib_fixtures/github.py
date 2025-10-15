# -*- coding: utf-8 -*-
#
# Copyright (C) 2025 CERN.
#
# Invenio-Github is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
"""Fixture test impl for GitHub."""

import os
from base64 import b64encode
from io import BytesIO
from typing import Any, Iterator
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import github3
import github3.repos
import github3.repos.hook
import github3.users

from invenio_vcs.contrib.github import GitHubProviderFactory
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


def github_user_metadata(
    id: int, display_name: str | None, login, email=None, bio=True
):
    """Github user fixture generator."""
    username = login

    user = {
        "avatar_url": "https://avatars.githubusercontent.com/u/7533764?",
        "collaborators": 0,
        "created_at": "2014-05-09T12:26:44Z",
        "disk_usage": 0,
        "events_url": "https://api.github.com/users/%s/events{/privacy}" % username,
        "followers": 0,
        "followers_url": "https://api.github.com/users/%s/followers" % username,
        "following": 0,
        "following_url": "https://api.github.com/users/%s/"
        "following{/other_user}" % username,
        "gists_url": "https://api.github.com/users/%s/gists{/gist_id}" % username,
        "gravatar_id": "12345678",
        "html_url": "https://github.com/%s" % username,
        "id": id,
        "login": "%s" % username,
        "organizations_url": "https://api.github.com/users/%s/orgs" % username,
        "owned_private_repos": 0,
        "plan": {
            "collaborators": 0,
            "name": "free",
            "private_repos": 0,
            "space": 307200,
        },
        "private_gists": 0,
        "public_gists": 0,
        "public_repos": 0,
        "received_events_url": "https://api.github.com/users/%s/"
        "received_events" % username,
        "repos_url": "https://api.github.com/users/%s/repos" % username,
        "site_admin": False,
        "starred_url": "https://api.github.com/users/%s/"
        "starred{/owner}{/repo}" % username,
        "subscriptions_url": "https://api.github.com/users/%s/"
        "subscriptions" % username,
        "total_private_repos": 0,
        "type": "User",
        "updated_at": "2014-05-09T12:26:44Z",
        "url": "https://api.github.com/users/%s" % username,
        "hireable": False,
        "location": "Geneve",
    }

    if bio:
        user.update(
            {
                "bio": "Software Engineer at CERN",
                "blog": "http://www.cern.ch",
                "company": "CERN",
                "name": display_name,
            }
        )

    if email is not None:
        user.update(
            {
                "email": email,
            }
        )

    return user


def github_repo_metadata(
    owner_username: str,
    owner_id: int,
    repo_name: str,
    repo_id: int,
    default_branch: str,
):
    """Github repository fixture generator."""
    repo_url = "%s/%s" % (owner_username, repo_name)

    return {
        "archive_url": "https://api.github.com/repos/%s/"
        "{archive_format}{/ref}" % repo_url,
        "assignees_url": "https://api.github.com/repos/%s/"
        "assignees{/user}" % repo_url,
        "blobs_url": "https://api.github.com/repos/%s/git/blobs{/sha}" % repo_url,
        "branches_url": "https://api.github.com/repos/%s/"
        "branches{/branch}" % repo_url,
        "clone_url": "https://github.com/%s.git" % repo_url,
        "collaborators_url": "https://api.github.com/repos/%s/"
        "collaborators{/collaborator}" % repo_url,
        "comments_url": "https://api.github.com/repos/%s/"
        "comments{/number}" % repo_url,
        "commits_url": "https://api.github.com/repos/%s/commits{/sha}" % repo_url,
        "compare_url": "https://api.github.com/repos/%s/compare/"
        "{base}...{head}" % repo_url,
        "contents_url": "https://api.github.com/repos/%s/contents/{+path}" % repo_url,
        "contributors_url": "https://api.github.com/repos/%s/contributors" % repo_url,
        "created_at": "2012-10-29T10:24:02Z",
        "default_branch": default_branch,
        "description": "",
        "downloads_url": "https://api.github.com/repos/%s/downloads" % repo_url,
        "events_url": "https://api.github.com/repos/%s/events" % repo_url,
        "fork": False,
        "forks": 0,
        "forks_count": 0,
        "forks_url": "https://api.github.com/repos/%s/forks" % repo_url,
        "full_name": repo_url,
        "git_commits_url": "https://api.github.com/repos/%s/git/"
        "commits{/sha}" % repo_url,
        "git_refs_url": "https://api.github.com/repos/%s/git/refs{/sha}" % repo_url,
        "git_tags_url": "https://api.github.com/repos/%s/git/tags{/sha}" % repo_url,
        "git_url": "git://github.com/%s.git" % repo_url,
        "has_downloads": True,
        "has_issues": True,
        "has_wiki": True,
        "homepage": None,
        "hooks_url": "https://api.github.com/repos/%s/hooks" % repo_url,
        "html_url": "https://github.com/%s" % repo_url,
        "id": repo_id,
        "issue_comment_url": "https://api.github.com/repos/%s/issues/"
        "comments/{number}" % repo_url,
        "issue_events_url": "https://api.github.com/repos/%s/issues/"
        "events{/number}" % repo_url,
        "issues_url": "https://api.github.com/repos/%s/issues{/number}" % repo_url,
        "keys_url": "https://api.github.com/repos/%s/keys{/key_id}" % repo_url,
        "labels_url": "https://api.github.com/repos/%s/labels{/name}" % repo_url,
        "language": None,
        "languages_url": "https://api.github.com/repos/%s/languages" % repo_url,
        "merges_url": "https://api.github.com/repos/%s/merges" % repo_url,
        "milestones_url": "https://api.github.com/repos/%s/"
        "milestones{/number}" % repo_url,
        "mirror_url": None,
        "name": "altantis-conf",
        "notifications_url": "https://api.github.com/repos/%s/"
        "notifications{?since,all,participating}",
        "open_issues": 0,
        "open_issues_count": 0,
        "owner": {
            "avatar_url": "https://avatars.githubusercontent.com/u/1234?",
            "events_url": "https://api.github.com/users/%s/"
            "events{/privacy}" % owner_username,
            "followers_url": "https://api.github.com/users/%s/followers"
            % owner_username,
            "following_url": "https://api.github.com/users/%s/"
            "following{/other_user}" % owner_username,
            "gists_url": "https://api.github.com/users/%s/gists{/gist_id}"
            % owner_username,
            "gravatar_id": "1234",
            "html_url": "https://github.com/%s" % owner_username,
            "id": owner_id,
            "login": "%s" % owner_username,
            "organizations_url": "https://api.github.com/users/%s/orgs"
            % owner_username,
            "received_events_url": "https://api.github.com/users/%s/"
            "received_events" % owner_username,
            "repos_url": "https://api.github.com/users/%s/repos" % owner_username,
            "site_admin": False,
            "starred_url": "https://api.github.com/users/%s/"
            "starred{/owner}{/repo}" % owner_username,
            "subscriptions_url": "https://api.github.com/users/%s/"
            "subscriptions" % owner_username,
            "type": "User",
            "url": "https://api.github.com/users/%s" % owner_username,
        },
        "permissions": {"admin": True, "pull": True, "push": True},
        "private": False,
        "pulls_url": "https://api.github.com/repos/%s/pulls{/number}" % repo_url,
        "pushed_at": "2012-10-29T10:28:08Z",
        "releases_url": "https://api.github.com/repos/%s/releases{/id}" % repo_url,
        "size": 104,
        "ssh_url": "git@github.com:%s.git" % repo_url,
        "stargazers_count": 0,
        "stargazers_url": "https://api.github.com/repos/%s/stargazers" % repo_url,
        "statuses_url": "https://api.github.com/repos/%s/statuses/{sha}" % repo_url,
        "subscribers_url": "https://api.github.com/repos/%s/subscribers" % repo_url,
        "subscription_url": "https://api.github.com/repos/%s/subscription" % repo_url,
        "svn_url": "https://github.com/%s" % repo_url,
        "tags_url": "https://api.github.com/repos/%s/tags" % repo_url,
        "teams_url": "https://api.github.com/repos/%s/teams" % repo_url,
        "trees_url": "https://api.github.com/repos/%s/git/trees{/sha}" % repo_url,
        "updated_at": "2013-10-25T11:30:04Z",
        "url": "https://api.github.com/repos/%s" % repo_url,
        "watchers": 0,
        "watchers_count": 0,
        "deployments_url": "https://api.github.com/repos/%s/deployments" % repo_url,
        "archived": False,
        "has_pages": False,
        "has_projects": False,
        "network_count": 0,
        "subscribers_count": 0,
    }


def github_zipball():
    """Github repository ZIP fixture."""
    memfile = BytesIO()
    zipfile = ZipFile(memfile, "w")
    zipfile.writestr("test.txt", "hello world")
    zipfile.close()
    memfile.seek(0)
    return memfile


def github_webhook_payload(
    sender, repo, repo_id, default_branch: str, tag: str = "v1.0"
):
    """Github payload fixture generator."""
    c = dict(repo=repo, user=sender, url="%s/%s" % (sender, repo), id="4321", tag=tag)

    return {
        "action": "published",
        "release": {
            "url": "https://api.github.com/repos/%(url)s/releases/%(id)s" % c,
            "assets_url": "https://api.github.com/repos/%(url)s/releases/"
            "%(id)s/assets" % c,
            "upload_url": "https://uploads.github.com/repos/%(url)s/"
            "releases/%(id)s/assets{?name}" % c,
            "html_url": "https://github.com/%(url)s/releases/tag/%(tag)s" % c,
            "id": int(c["id"]),
            "tag_name": c["tag"],
            "target_commitish": default_branch,
            "name": "Release name",
            "body": "",
            "draft": False,
            "author": {
                "login": "%(user)s" % c,
                "id": 1698163,
                "avatar_url": "https://avatars.githubusercontent.com/u/12345",
                "gravatar_id": "12345678",
                "url": "https://api.github.com/users/%(user)s" % c,
                "html_url": "https://github.com/%(user)s" % c,
                "followers_url": "https://api.github.com/users/%(user)s/"
                "followers" % c,
                "following_url": "https://api.github.com/users/%(user)s/"
                "following{/other_user}" % c,
                "gists_url": "https://api.github.com/users/%(user)s/"
                "gists{/gist_id}" % c,
                "starred_url": "https://api.github.com/users/%(user)s/"
                "starred{/owner}{/repo}" % c,
                "subscriptions_url": "https://api.github.com/users/%(user)s/"
                "subscriptions" % c,
                "organizations_url": "https://api.github.com/users/%(user)s/"
                "orgs" % c,
                "repos_url": "https://api.github.com/users/%(user)s/repos" % c,
                "events_url": "https://api.github.com/users/%(user)s/"
                "events{/privacy}" % c,
                "received_events_url": "https://api.github.com/users/"
                "%(user)s/received_events" % c,
                "type": "User",
                "site_admin": False,
            },
            "prerelease": False,
            "created_at": "2014-02-26T08:13:42Z",
            "published_at": "2014-02-28T13:55:32Z",
            "assets": [],
            "tarball_url": "https://api.github.com/repos/%(url)s/"
            "tarball/%(tag)s" % c,
            "zipball_url": "https://api.github.com/repos/%(url)s/"
            "zipball/%(tag)s" % c,
        },
        "repository": {
            "id": repo_id,
            "name": repo,
            "full_name": "%(url)s" % c,
            "owner": {
                "login": "%(user)s" % c,
                "id": 1698163,
                "avatar_url": "https://avatars.githubusercontent.com/u/" "1698163",
                "gravatar_id": "bbc951080061fc48cae0279d27f3c015",
                "url": "https://api.github.com/users/%(user)s" % c,
                "html_url": "https://github.com/%(user)s" % c,
                "followers_url": "https://api.github.com/users/%(user)s/"
                "followers" % c,
                "following_url": "https://api.github.com/users/%(user)s/"
                "following{/other_user}" % c,
                "gists_url": "https://api.github.com/users/%(user)s/"
                "gists{/gist_id}" % c,
                "starred_url": "https://api.github.com/users/%(user)s/"
                "starred{/owner}{/repo}" % c,
                "subscriptions_url": "https://api.github.com/users/%(user)s/"
                "subscriptions" % c,
                "organizations_url": "https://api.github.com/users/%(user)s/"
                "orgs" % c,
                "repos_url": "https://api.github.com/users/%(user)s/" "repos" % c,
                "events_url": "https://api.github.com/users/%(user)s/"
                "events{/privacy}" % c,
                "received_events_url": "https://api.github.com/users/"
                "%(user)s/received_events" % c,
                "type": "User",
                "site_admin": False,
            },
            "private": False,
            "html_url": "https://github.com/%(url)s" % c,
            "description": "Repo description.",
            "fork": True,
            "url": "https://api.github.com/repos/%(url)s" % c,
            "forks_url": "https://api.github.com/repos/%(url)s/forks" % c,
            "keys_url": "https://api.github.com/repos/%(url)s/" "keys{/key_id}" % c,
            "collaborators_url": "https://api.github.com/repos/%(url)s/"
            "collaborators{/collaborator}" % c,
            "teams_url": "https://api.github.com/repos/%(url)s/teams" % c,
            "hooks_url": "https://api.github.com/repos/%(url)s/hooks" % c,
            "issue_events_url": "https://api.github.com/repos/%(url)s/"
            "issues/events{/number}" % c,
            "events_url": "https://api.github.com/repos/%(url)s/events" % c,
            "assignees_url": "https://api.github.com/repos/%(url)s/"
            "assignees{/user}" % c,
            "branches_url": "https://api.github.com/repos/%(url)s/"
            "branches{/branch}" % c,
            "tags_url": "https://api.github.com/repos/%(url)s/tags" % c,
            "blobs_url": "https://api.github.com/repos/%(url)s/git/" "blobs{/sha}" % c,
            "git_tags_url": "https://api.github.com/repos/%(url)s/git/"
            "tags{/sha}" % c,
            "git_refs_url": "https://api.github.com/repos/%(url)s/git/"
            "refs{/sha}" % c,
            "trees_url": "https://api.github.com/repos/%(url)s/git/" "trees{/sha}" % c,
            "statuses_url": "https://api.github.com/repos/%(url)s/"
            "statuses/{sha}" % c,
            "languages_url": "https://api.github.com/repos/%(url)s/" "languages" % c,
            "stargazers_url": "https://api.github.com/repos/%(url)s/" "stargazers" % c,
            "contributors_url": "https://api.github.com/repos/%(url)s/"
            "contributors" % c,
            "subscribers_url": "https://api.github.com/repos/%(url)s/"
            "subscribers" % c,
            "subscription_url": "https://api.github.com/repos/%(url)s/"
            "subscription" % c,
            "commits_url": "https://api.github.com/repos/%(url)s/" "commits{/sha}" % c,
            "git_commits_url": "https://api.github.com/repos/%(url)s/git/"
            "commits{/sha}" % c,
            "comments_url": "https://api.github.com/repos/%(url)s/"
            "comments{/number}" % c,
            "issue_comment_url": "https://api.github.com/repos/%(url)s/"
            "issues/comments/{number}" % c,
            "contents_url": "https://api.github.com/repos/%(url)s/"
            "contents/{+path}" % c,
            "compare_url": "https://api.github.com/repos/%(url)s/"
            "compare/{base}...{head}" % c,
            "merges_url": "https://api.github.com/repos/%(url)s/merges" % c,
            "archive_url": "https://api.github.com/repos/%(url)s/"
            "{archive_format}{/ref}" % c,
            "downloads_url": "https://api.github.com/repos/%(url)s/" "downloads" % c,
            "issues_url": "https://api.github.com/repos/%(url)s/" "issues{/number}" % c,
            "pulls_url": "https://api.github.com/repos/%(url)s/" "pulls{/number}" % c,
            "milestones_url": "https://api.github.com/repos/%(url)s/"
            "milestones{/number}" % c,
            "notifications_url": "https://api.github.com/repos/%(url)s/"
            "notifications{?since,all,participating}" % c,
            "labels_url": "https://api.github.com/repos/%(url)s/" "labels{/name}" % c,
            "releases_url": "https://api.github.com/repos/%(url)s/" "releases{/id}" % c,
            "created_at": "2014-02-26T07:39:11Z",
            "updated_at": "2014-02-28T13:55:32Z",
            "pushed_at": "2014-02-28T13:55:32Z",
            "git_url": "git://github.com/%(url)s.git" % c,
            "ssh_url": "git@github.com:%(url)s.git" % c,
            "clone_url": "https://github.com/%(url)s.git" % c,
            "svn_url": "https://github.com/%(url)s" % c,
            "homepage": None,
            "size": 388,
            "stargazers_count": 0,
            "watchers_count": 0,
            "language": "Python",
            "has_issues": False,
            "has_downloads": True,
            "has_wiki": True,
            "forks_count": 0,
            "mirror_url": None,
            "open_issues_count": 0,
            "forks": 0,
            "open_issues": 0,
            "watchers": 0,
            "default_branch": default_branch,
            "master_branch": default_branch,
        },
        "sender": {
            "login": "%(user)s" % c,
            "id": 1698163,
            "avatar_url": "https://avatars.githubusercontent.com/u/1234578",
            "gravatar_id": "12345678",
            "url": "https://api.github.com/users/%(user)s" % c,
            "html_url": "https://github.com/%(user)s" % c,
            "followers_url": "https://api.github.com/users/%(user)s/" "followers" % c,
            "following_url": "https://api.github.com/users/%(user)s/"
            "following{/other_user}" % c,
            "gists_url": "https://api.github.com/users/%(user)s/" "gists{/gist_id}" % c,
            "starred_url": "https://api.github.com/users/%(user)s/"
            "starred{/owner}{/repo}" % c,
            "subscriptions_url": "https://api.github.com/users/%(user)s/"
            "subscriptions" % c,
            "organizations_url": "https://api.github.com/users/%(user)s/" "orgs" % c,
            "repos_url": "https://api.github.com/users/%(user)s/repos" % c,
            "events_url": "https://api.github.com/users/%(user)s/"
            "events{/privacy}" % c,
            "received_events_url": "https://api.github.com/users/%(user)s/"
            "received_events" % c,
            "type": "User",
            "site_admin": False,
        },
    }


def github_organization_metadata(login):
    """Github organization fixture generator."""
    return {
        "login": login,
        "id": 1234,
        "url": "https://api.github.com/orgs/%s" % login,
        "repos_url": "https://api.github.com/orgs/%s/repos" % login,
        "events_url": "https://api.github.com/orgs/%s/events" % login,
        "members_url": "https://api.github.com/orgs/%s/" "members{/member}" % login,
        "public_members_url": "https://api.github.com/orgs/%s/"
        "public_members{/member}" % login,
        "avatar_url": "https://avatars.githubusercontent.com/u/1234?",
    }


def github_collaborator_metadata(admin: bool, login: str, id: int):
    """Generate metadata for a repo collaborator."""
    return {
        "login": login,
        "id": id,
        "node_id": "MDQ6VXNlcjE=",
        "avatar_url": "https://github.com/images/error/octocat_happy.gif",
        "gravatar_id": "",
        "url": "https://api.github.com/users/%s" % login,
        "html_url": "https://github.com/%s" % login,
        "followers_url": "https://api.github.com/users/%s/followers" % login,
        "following_url": "https://api.github.com/users/%s/following{/other_user}"
        % login,
        "gists_url": "https://api.github.com/users/%s/gists{/gist_id}" % login,
        "starred_url": "https://api.github.com/users/%s/starred{/owner}{/repo}" % login,
        "subscriptions_url": "https://api.github.com/users/%s/subscriptions" % login,
        "organizations_url": "https://api.github.com/users/%s/orgs" % login,
        "repos_url": "https://api.github.com/users/%s/repos" % login,
        "events_url": "https://api.github.com/users/%s/events{/privacy}" % login,
        "received_events_url": "https://api.github.com/users/%s/received_events"
        % login,
        "type": "User",
        "site_admin": False,
        "permissions": {
            "pull": True,
            "triage": True,
            "push": True,
            "maintain": True,
            "admin": admin,
        },
        "role_name": "write",
    }


def github_contributor_metadata(id: int, login: str, contributions: int):
    """Generate metadata for a repo contributor."""
    return {
        "login": login,
        "id": id,
        "node_id": "MDQ6VXNlcjE=",
        "avatar_url": "https://github.com/images/error/octocat_happy.gif",
        "gravatar_id": "",
        "url": "https://api.github.com/users/%s" % login,
        "html_url": "https://github.com/%s" % login,
        "followers_url": "https://api.github.com/users/%s/followers" % login,
        "following_url": "https://api.github.com/users/%s/following{/other_user}"
        % login,
        "gists_url": "https://api.github.com/users/%s/gists{/gist_id}" % login,
        "starred_url": "https://api.github.com/users/%s/starred{/owner}{/repo}" % login,
        "subscriptions_url": "https://api.github.com/users/%s/subscriptions" % login,
        "organizations_url": "https://api.github.com/users/%s/orgs" % login,
        "repos_url": "https://api.github.com/users/%s/repos" % login,
        "events_url": "https://api.github.com/users/%s/events{/privacy}" % login,
        "received_events_url": "https://api.github.com/users/%s/received_events"
        % login,
        "type": "User",
        "site_admin": False,
        "contributions": contributions,
    }


def github_webhook_metadata(id: int, url: str, repo_name: str):
    """Generate metadata for a repo webhook."""
    return {
        "type": "Repository",
        "id": id,
        "name": "web",
        "active": True,
        "events": ["push", "pull_request"],
        "config": {
            "content_type": "json",
            "insecure_ssl": "0",
            "url": url,
        },
        "updated_at": "2019-06-03T00:57:16Z",
        "created_at": "2019-06-03T00:57:16Z",
        "url": "https://api.github.com/repos/%s/hooks/%d" % (repo_name, id),
        "test_url": "https://api.github.com/repos/%s/hooks/%d/test" % (repo_name, id),
        "ping_url": "https://api.github.com/repos/%s/hooks/%d/pings" % (repo_name, id),
        "deliveries_url": "https://api.github.com/repos/%s/hooks/%d/deliveries"
        % (repo_name, id),
        "last_response": {"code": None, "status": "unused", "message": None},
    }


def github_release_metadata(
    id: int,
    repo_name: str,
    tag_name: str,
    release_name: str | None,
    release_description: str | None,
):
    """Generate metadata for a release."""
    return {
        "url": "https://api.github.com/repos/%s/releases/%d" % (repo_name, id),
        "html_url": "https://github.com/%s/releases/%s" % (repo_name, tag_name),
        "assets_url": "https://api.github.com/repos/%s/releases/%d/assets"
        % (repo_name, id),
        "upload_url": "https://uploads.github.com/repos/%s/releases/%d/assets{?name,label}"
        % (repo_name, id),
        "tarball_url": "https://api.github.com/repos/%s/tarball/%s"
        % (repo_name, tag_name),
        "zipball_url": "https://api.github.com/repos/%s/zipball/%s"
        % (repo_name, tag_name),
        "id": id,
        "node_id": "MDc6UmVsZWFzZTE=",
        "tag_name": tag_name,
        "target_commitish": "master",
        "name": release_name,
        "body": release_description,
        "draft": False,
        "prerelease": False,
        "immutable": True,
        "created_at": "2013-02-27T19:35:32Z",
        "published_at": "2013-02-27T19:35:32Z",
        "author": {
            "login": "octocat",
            "id": 1,
            "node_id": "MDQ6VXNlcjE=",
            "avatar_url": "https://github.com/images/error/octocat_happy.gif",
            "gravatar_id": "",
            "url": "https://api.github.com/users/octocat",
            "html_url": "https://github.com/octocat",
            "followers_url": "https://api.github.com/users/octocat/followers",
            "following_url": "https://api.github.com/users/octocat/following{/other_user}",
            "gists_url": "https://api.github.com/users/octocat/gists{/gist_id}",
            "starred_url": "https://api.github.com/users/octocat/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.github.com/users/octocat/subscriptions",
            "organizations_url": "https://api.github.com/users/octocat/orgs",
            "repos_url": "https://api.github.com/users/octocat/repos",
            "events_url": "https://api.github.com/users/octocat/events{/privacy}",
            "received_events_url": "https://api.github.com/users/octocat/received_events",
            "type": "User",
            "site_admin": False,
        },
        "assets": [
            {
                "url": "https://api.github.com/repos/%s/releases/assets/1" % repo_name,
                "browser_download_url": "https://github.com/%s/releases/download/%s/example.zip"
                % (repo_name, tag_name),
                "id": 1,
                "node_id": "MDEyOlJlbGVhc2VBc3NldDE=",
                "name": "example.zip",
                "label": "short description",
                "state": "uploaded",
                "content_type": "application/zip",
                "size": 1024,
                "digest": "sha256:2151b604e3429bff440b9fbc03eb3617bc2603cda96c95b9bb05277f9ddba255",
                "download_count": 42,
                "created_at": "2013-02-27T19:35:32Z",
                "updated_at": "2013-02-27T19:35:32Z",
                "uploader": {
                    "login": "octocat",
                    "id": 1,
                    "node_id": "MDQ6VXNlcjE=",
                    "avatar_url": "https://github.com/images/error/octocat_happy.gif",
                    "gravatar_id": "",
                    "url": "https://api.github.com/users/octocat",
                    "html_url": "https://github.com/octocat",
                    "followers_url": "https://api.github.com/users/octocat/followers",
                    "following_url": "https://api.github.com/users/octocat/following{/other_user}",
                    "gists_url": "https://api.github.com/users/octocat/gists{/gist_id}",
                    "starred_url": "https://api.github.com/users/octocat/starred{/owner}{/repo}",
                    "subscriptions_url": "https://api.github.com/users/octocat/subscriptions",
                    "organizations_url": "https://api.github.com/users/octocat/orgs",
                    "repos_url": "https://api.github.com/users/octocat/repos",
                    "events_url": "https://api.github.com/users/octocat/events{/privacy}",
                    "received_events_url": "https://api.github.com/users/octocat/received_events",
                    "type": "User",
                    "site_admin": False,
                },
            }
        ],
    }


def github_webhook_payload(
    id: int,
    tag_name: str,
    release_name: str | None,
    release_description: str | None,
    repo_id: int,
    repo_name: str,
    repo_owner_id: int,
    repo_owner_username: str,
    repo_default_branch: str,
):
    """Generate sample payload for a release event webhook."""
    return {
        "action": "created",
        "release": github_release_metadata(
            id, repo_name, tag_name, release_name, release_description
        ),
        "repository": github_repo_metadata(
            repo_owner_username, repo_owner_id, repo_name, repo_id, repo_default_branch
        ),
    }


class GitHubPatcher(TestProviderPatcher):
    """Patch the GitHub API primitives to avoid real API calls and return test data instead."""

    @staticmethod
    def provider_factory() -> RepositoryServiceProviderFactory:
        """GitHub provider factory."""
        return GitHubProviderFactory(
            base_url="https://github.com",
            webhook_receiver_url="http://localhost:5000/api/receivers/github/events/?access_token={token}",
        )

    @staticmethod
    def test_webhook_payload(
        generic_repository: GenericRepository,
        generic_release: GenericRelease,
        generic_repo_owner: GenericOwner,
    ) -> dict[str, Any]:
        """Return a sample webhook payload."""
        return github_webhook_payload(
            int(generic_release.id),
            generic_release.tag_name,
            generic_release.name,
            generic_release.body,
            int(generic_repository.id),
            generic_repository.full_name,
            int(generic_repo_owner.id),
            generic_repo_owner.path_name,
            generic_repository.default_branch,
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
        mock_api = MagicMock()
        mock_api.session = MagicMock()
        mock_api.me.return_value = github3.users.User(
            github_user_metadata(
                id=int(test_generic_user.id),
                display_name=test_generic_user.display_name,
                login=test_generic_user.username,
                email="%s@inveniosoftware.org" % test_generic_user.username,
            ),
            mock_api.session,
        )

        contributors: list[github3.users.Contributor] = []
        for generic_contributor in test_generic_contributors:
            contributor = github3.users.Contributor(
                github_contributor_metadata(
                    int(generic_contributor.id),
                    generic_contributor.username,
                    generic_contributor.contributions_count or 0,
                ),
                mock_api.session,
            )
            contributor.refresh = MagicMock(
                return_value=github3.users.User(
                    github_user_metadata(
                        int(generic_contributor.id),
                        generic_contributor.display_name,
                        generic_contributor.username,
                        "%s@inveniosoftware.org" % generic_contributor.username,
                    ),
                    mock_api.session,
                )
            )
            contributors.append(contributor)

        collaborators: list[github3.users.Collaborator] = []
        for collaborator in test_collaborators:
            collaborators.append(
                github3.users.Collaborator(
                    github_collaborator_metadata(
                        collaborator["admin"],
                        collaborator["username"],
                        int(collaborator["id"]),
                    ),
                    mock_api.session,
                )
            )

        repos: dict[int, github3.repos.Repository] = {}
        for generic_repo in test_generic_repositories:
            repo = github3.repos.ShortRepository(
                github_repo_metadata(
                    "auser",
                    1,
                    generic_repo.full_name,
                    int(generic_repo.id),
                    generic_repo.default_branch,
                ),
                mock_api.session,
            )

            hooks: list[github3.repos.hook.Hook] = []
            for hook in test_generic_webhooks:
                if hook.id != generic_repo.id:
                    continue

                hooks.append(
                    github3.repos.hook.Hook(
                        github_webhook_metadata(
                            int(hook.id), hook.url, generic_repo.full_name
                        ),
                        mock_api.session,
                    )
                )

            repo.hooks = MagicMock(return_value=hooks)
            repo.file_contents = MagicMock(return_value=None)
            # Mock hook creation to return the hook id '12345'
            hook_instance = MagicMock()
            hook_instance.id = 12345
            repo.create_hook = MagicMock(return_value=hook_instance)
            repo.collaborators = MagicMock(return_value=collaborators)
            repo.contributors = MagicMock(return_value=contributors)

            def mock_file_contents(path: str, ref: str):
                if path == test_file["path"]:
                    # Mock github3.contents.Content with file data
                    return MagicMock(decoded=test_file["content"].encode("ascii"))
                raise github3.exceptions.NotFoundError(MagicMock(status_code=404))

            repo.file_contents = MagicMock(side_effect=mock_file_contents)

            repos[int(generic_repo.id)] = repo

        repos_by_name = {r.full_name: r for r in repos.values()}
        mock_api.repositories.return_value = repos.values()

        def mock_repo_with_id(id):
            return repos.get(id)

        def mock_repo_by_name(owner, name):
            return repos_by_name.get("/".join((owner, name)))

        def mock_head_status_by_repo_url(url, **kwargs):
            url_specific_refs_tags = (
                "https://github.com/auser/repo-2/zipball/refs/tags/v1.0-tag-and-branch"
            )
            if url.endswith("v1.0-tag-and-branch") and url != url_specific_refs_tags:
                return MagicMock(
                    status_code=300,
                    links={"alternate": {"url": url_specific_refs_tags}},
                )
            else:
                return MagicMock(status_code=200, url=url)

        mock_api.repository_with_id.side_effect = mock_repo_with_id
        mock_api.repository.side_effect = mock_repo_by_name
        mock_api.markdown.side_effect = lambda x: x
        mock_api.session.head.side_effect = mock_head_status_by_repo_url
        mock_api.session.get.return_value = MagicMock(raw=github_zipball())

        with patch("invenio_vcs.contrib.github.GitHubProvider._gh", new=mock_api):
            yield self.provider
