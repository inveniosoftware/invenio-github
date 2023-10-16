# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2023 CERN.
#
# Invenio is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Invenio-GitHub errors."""


class GitHubError(Exception):
    """General GitHub error."""


class RepositoryAccessError(GitHubError):
    """Repository access permissions error."""

    message = "The user cannot access the github repository"

    def __init__(self, user=None, repo=None, repo_id=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.user = user
        self.repo = repo
        self.repo_id = repo_id


class RepositoryDisabledError(GitHubError):
    """Repository access permissions error."""

    message = "This repository is not enabled for webhooks."

    def __init__(self, repo=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.repo = repo


class RepositoryNotFoundError(GitHubError):
    """Repository not found error."""

    message = "The repository does not exist."

    def __init__(self, repo=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.repo = repo


class InvalidSenderError(GitHubError):
    """Invalid release sender error."""

    message = "Invalid sender for event"

    def __init__(self, event=None, user=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.event = event
        self.user = user


class ReleaseAlreadyReceivedError(GitHubError):
    """Invalid release sender error."""

    message = "The release has already been received."

    def __init__(self, release=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.release = release


class CustomGitHubMetadataError(GitHubError):
    """Invalid Custom GitHub Metadata file."""

    message = "The metadata file is not valid JSON."

    def __init__(self, file=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.file = file


class GithubTokenNotFound(GitHubError):
    """Oauth session token was not found."""

    message = "The oauth session token was not found."

    def __init__(self, user=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.user = user


class RemoteAccountNotFound(GitHubError):
    """Remote account for the user is not setup."""

    message = "RemoteAccount not found for user"

    def __init__(self, user=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.user = user


class RemoteAccountDataNotSet(GitHubError):
    """Remote account extra data for the user is not set."""

    message = "RemoteAccount extra data not set for user."

    def __init__(self, user=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.user = user


class ReleaseNotFound(GitHubError):
    """Release does not exist."""

    message = "Release does not exist."

    def __init__(self, message=None):
        """Constructor."""
        super().__init__(message or self.message)
