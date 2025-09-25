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

"""Configuration for GitHub module."""

from typing import TYPE_CHECKING

from flask import current_app

if TYPE_CHECKING:
    from invenio_vcs.providers import RepositoryServiceProviderFactory

VCS_PROVIDERS = []

VCS_RELEASE_CLASS = "invenio_vcs.service:VCSRelease"
"""GitHubRelease class to be used for release handling."""

VCS_TEMPLATE_INDEX = "invenio_vcs/settings/index.html"
"""Repositories list template."""

VCS_TEMPLATE_VIEW = "invenio_vcs/settings/view.html"
"""Repository detail view template."""

VCS_ERROR_HANDLERS = None
"""Definition of the way specific exceptions are handled."""

VCS_MAX_CONTRIBUTORS_NUMBER = 30
"""Max number of contributors of a release to be retrieved from Github."""

VCS_CITATION_FILE = None
"""Citation file name."""

VCS_CITATION_METADATA_SCHEMA = None
"""Citation metadata schema."""

VCS_ZIPBALL_TIMEOUT = 300
"""Timeout for the zipball download, in seconds."""


def get_provider_list(app=current_app) -> list["RepositoryServiceProviderFactory"]:
    return app.config["VCS_PROVIDERS"]


def get_provider_by_id(id: str) -> "RepositoryServiceProviderFactory":
    providers = get_provider_list()
    for provider in providers:
        if id == provider.id:
            return provider
    raise Exception(f"VCS provider with ID {id} not registered")
