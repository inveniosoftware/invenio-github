# SPDX-FileCopyrightText: 2023-2025 CERN.
# SPDX-FileCopyrightText: 2024 KTH Royal Institute of Technology.
# SPDX-License-Identifier: MIT

"""Invenio-GitHub errors."""

from invenio_i18n import gettext as _


class GitHubError(Exception):
    """General GitHub error."""


class RepositoryAccessError(GitHubError):
    """Repository access permissions error."""

    message = _("The user cannot access the github repository")

    def __init__(self, user=None, repo=None, repo_id=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.message = message
        self.user = user
        self.repo = repo
        self.repo_id = repo_id


class RepositoryDisabledError(GitHubError):
    """Repository access permissions error."""

    message = _("This repository is not enabled for webhooks.")

    def __init__(self, repo=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.repo = repo


class RepositoryNotFoundError(GitHubError):
    """Repository not found error."""

    message = _("The repository does not exist.")

    def __init__(self, repo=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.repo = repo


class InvalidSenderError(GitHubError):
    """Invalid release sender error."""

    message = _("Invalid sender for event")

    def __init__(self, event=None, user=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.event = event
        self.user = user


class ReleaseAlreadyReceivedError(GitHubError):
    """Invalid release sender error."""

    message = _("The release has already been received.")

    def __init__(self, release=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.release = release


class CustomGitHubMetadataError(GitHubError):
    """Invalid Custom GitHub Metadata file."""

    message = _("The metadata file is not valid JSON.")

    def __init__(self, file=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.file = file


class GithubTokenNotFound(GitHubError):
    """Oauth session token was not found."""

    message = _("The oauth session token was not found.")

    def __init__(self, user=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.user = user


class RemoteAccountNotFound(GitHubError):
    """Remote account for the user is not setup."""

    message = _("RemoteAccount not found for user")

    def __init__(self, user=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.user = user


class RemoteAccountDataNotSet(GitHubError):
    """Remote account extra data for the user is not set."""

    message = _("RemoteAccount extra data not set for user.")

    def __init__(self, user=None, message=None):
        """Constructor."""
        super().__init__(message or self.message)
        self.user = user


class ReleaseNotFound(GitHubError):
    """Release does not exist."""

    message = _("Release does not exist.")

    def __init__(self, message=None):
        """Constructor."""
        super().__init__(message or self.message)


class UnexpectedGithubResponse(GitHubError):
    """Request to Github API returned an unexpected error."""

    message = _("Github API returned an unexpected error.")

    def __init__(self, message=None):
        """Constructor."""
        super().__init__(message or self.message)


class ReleaseZipballFetchError(GitHubError):
    """Error fetching release zipball file."""

    message = _("Error fetching release zipball file.")

    def __init__(self, message=None):
        """Constructor."""
        super().__init__(message or self.message)
