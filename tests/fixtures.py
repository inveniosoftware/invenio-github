# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2023 CERN.
#
# Invenio is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Invenio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio. If not, see <http://www.gnu.org/licenses/>.
#
# In applying this licence, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as an Intergovernmental Organization
# or submit itself to any jurisdiction.

"""Define fixtures for tests."""
import os
from base64 import b64encode
from zipfile import ZipFile

from six import BytesIO

from invenio_github.api import GitHubRelease
from invenio_github.models import ReleaseStatus


class TestGithubRelease(GitHubRelease):
    """Implements GithubRelease with test methods."""

    def publish(self):
        """Sets release status to published.

        Does not create a "real" record, as this only used to test the API.
        """
        self.release_object.status = ReleaseStatus.PUBLISHED
        self.release_object.record_id = "445aaacd-9de1-41ab-af52-25ab6cb93df7"
        return {}

    def process_release(self):
        """Processes a release."""
        self.publish()
        return {}

    def resolve_record(self):
        """Resolves a record.

        Returns an empty object as this class is only used to test the API.
        """
        return {}


#
# Fixture generators
#
def github_user_metadata(login, email=None, bio=True):
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
        "id": 1234,
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
                "name": "Lars Holm Nielsen",
            }
        )

    if email is not None:
        user.update(
            {
                "email": email,
            }
        )

    return user


def github_repo_metadata(owner, repo, repo_id):
    """Github repository fixture generator."""
    repo_url = "%s/%s" % (owner, repo)

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
        "default_branch": "master",
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
            "events_url": "https://api.github.com/users/%s/" "events{/privacy}" % owner,
            "followers_url": "https://api.github.com/users/%s/followers" % owner,
            "following_url": "https://api.github.com/users/%s/"
            "following{/other_user}" % owner,
            "gists_url": "https://api.github.com/users/%s/gists{/gist_id}" % owner,
            "gravatar_id": "1234",
            "html_url": "https://github.com/%s" % owner,
            "id": 1698163,
            "login": "%s" % owner,
            "organizations_url": "https://api.github.com/users/%s/orgs" % owner,
            "received_events_url": "https://api.github.com/users/%s/"
            "received_events" % owner,
            "repos_url": "https://api.github.com/users/%s/repos" % owner,
            "site_admin": False,
            "starred_url": "https://api.github.com/users/%s/"
            "starred{/owner}{/repo}" % owner,
            "subscriptions_url": "https://api.github.com/users/%s/"
            "subscriptions" % owner,
            "type": "User",
            "url": "https://api.github.com/users/%s" % owner,
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


def ZIPBALL():
    """Github repository ZIP fixture."""
    memfile = BytesIO()
    zipfile = ZipFile(memfile, "w")
    zipfile.writestr("test.txt", "hello world")
    zipfile.close()
    memfile.seek(0)
    return memfile


def PAYLOAD(sender, repo, repo_id, tag="v1.0"):
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
            "target_commitish": "master",
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
            "default_branch": "master",
            "master_branch": "master",
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


def ORG(login):
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


def github_file_contents(owner, repo, file_path, ref, data):
    """Github content fixture generator."""
    c = dict(
        url="%s/%s" % (owner, repo),
        owner=owner,
        repo=repo,
        file=file_path,
        ref=ref,
    )

    return {
        "_links": {
            "git": "https://api.github.com/repos/%(url)s/git/blobs/"
            "aaaffdfbead0b67bd6a5f5819c458a1215ecb0f6" % c,
            "html": "https://github.com/%(url)s/blob/%(ref)s/%(file)s" % c,
            "self": "https://api.github.com/repos/%(url)s/contents/"
            "%(file)s?ref=%(ref)s" % c,
        },
        "content": b64encode(data),
        "encoding": "base64",
        "git_url": "https://api.github.com/repos/%(url)s/git/blobs/"
        "aaaffdfbead0b67bd6a5f5819c458a1215ecb0f6" % c,
        "html_url": "https://github.com/%(url)s/blob/%(ref)s/%(file)s" % c,
        "name": os.path.basename(file_path),
        "path": file_path,
        "sha": "aaaffdfbead0b67bd6a5f5819c458a1215ecb0f6",
        "size": 1209,
        "type": "file",
        "url": "https://api.github.com/repos/%(url)s/contents/"
        "%(file)s?ref=%(ref)s" % c,
    }
