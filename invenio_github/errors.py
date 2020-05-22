# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016 CERN.
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

    message = u'The user cannot access the github repository'

    def __init__(self, user=None, repo=None, repo_id=None, message=None):
        """Constructor."""
        super(RepositoryAccessError, self).__init__(message or self.message)
        self.user = user
        self.repo = repo
        self.repo_id = repo_id


class RepositoryDisabledError(GitHubError):
    """Repository access permissions error."""

    message = u'This repository is not enabled for webhooks.'

    def __init__(self, repo=None, message=None):
        """Constructor."""
        super(RepositoryDisabledError, self).__init__(message or self.message)
        self.repo = repo


class InvalidSenderError(GitHubError):
    """Invalid release sender error."""

    message = u'Invalid sender for event'

    def __init__(self, event=None, user=None, message=None):
        """Constructor."""
        super(InvalidSenderError, self).__init__(message or self.message)
        self.event = event
        self.user = user


class ReleaseAlreadyReceivedError(GitHubError):
    """Invalid release sender error."""

    message = u'The release has already been received.'

    def __init__(self, release=None, message=None):
        """Constructor."""
        super(ReleaseAlreadyReceivedError, self).__init__(
            message or self.message)
        self.release = release


class CustomGitHubMetadataError(GitHubError):
    """Invalid Custom GitHub Metadata file."""

    message = u'The metadata file is not valid JSON.'

    def __init__(self, file=None, message=None):
        """Constructor."""
        super(CustomGitHubMetadataError, self).__init__(
            message or self.message)
        self.file = file
