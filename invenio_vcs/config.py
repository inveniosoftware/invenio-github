# -*- coding: utf-8 -*-
# This file is part of Invenio.
# Copyright (C) 2025 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Configuration for the VCS module."""

from typing import TYPE_CHECKING

from flask import current_app

if TYPE_CHECKING:
    from invenio_vcs.providers import RepositoryServiceProviderFactory

VCS_PROVIDERS = []

VCS_RELEASE_CLASS = "invenio_vcs.service:VCSRelease"
"""VCSRelease class to be used for release handling."""

VCS_TEMPLATE_INDEX = "invenio_vcs/settings/index.html"
"""Repositories list template."""

VCS_TEMPLATE_VIEW = "invenio_vcs/settings/view.html"
"""Repository detail view template."""

VCS_ERROR_HANDLERS = None
"""Definition of the way specific exceptions are handled."""

VCS_MAX_CONTRIBUTORS_NUMBER = 30
"""Max number of contributors of a release to be retrieved from vcs."""

VCS_CITATION_FILE = None
"""Citation file name."""

VCS_CITATION_METADATA_SCHEMA = None
"""Citation metadata schema."""

VCS_ZIPBALL_TIMEOUT = 300
"""Timeout for the zipball download, in seconds."""

VCS_SYNC_BATCH_SIZE = 20
"""Number of repositories to be processed in a single batch when syncing hooks and users.

If the user has more than 20 repositories, multiple tasks will be created,
syncing them in parallel. Thereby the sync process should finish in a timely
manner and we avoid timeouts on platforms like Zenodo.

Decrease this value if you experience task timeouts.
"""


def get_provider_list(app=current_app) -> list["RepositoryServiceProviderFactory"]:
    """Get a list of configured VCS provider factories."""
    return app.config["VCS_PROVIDERS"]


def get_provider_by_id(id: str) -> "RepositoryServiceProviderFactory":
    """Get a specific VCS provider by its registered ID."""
    providers = get_provider_list()
    for provider in providers:
        if id == provider.id:
            return provider
    raise Exception(f"VCS provider with ID {id} not registered")
