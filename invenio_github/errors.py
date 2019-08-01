# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016-2019 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Invenio-GitHub errors."""


class GitHubError(Exception):
    """General GitHub error."""


class RepositoryAccessError(GitHubError):
    """Repository access permissions error."""


class RepositoryDisabledError(GitHubError):
    """Repository access permissions error."""


class InvalidSenderError(GitHubError):
    """Invalid release sender error."""


class ReleaseAlreadyReceivedError(GitHubError):
    """Invalid release sender error."""


class CustomGitHubMetadataError(GitHubError):
    """Invalid Custom GitHub Metadata file."""
