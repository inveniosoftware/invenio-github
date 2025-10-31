# -*- coding: utf-8 -*-
# This file is part of Invenio.
# Copyright (C) 2025 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""You can use these options to configure the Invenio-VCS module.

Other than ``VCS_PROVIDERS``, they are all optional and configured with reasonable defaults.
"""

from typing import TYPE_CHECKING

from flask import current_app

if TYPE_CHECKING:
    from invenio_vcs.providers import RepositoryServiceProviderFactory

VCS_PROVIDERS = []
"""The list of RepositoryProviderFactory instances.

These will be visible to the user in their settings and they will be able to sync repositories
from all of them. Multiple instances of different providers as well as of the same provider
can be combined in this list, but each provider must have a unique ``id`` and ``credentials_key``.
"""

VCS_PROVIDER_CONFIG_DICT = {}
"""An optional dictionary of configuration overrides for RepositoryProviderFactory instances.

This makes it possible to specify configuration values via environment variables rather than as
class constructor parameters, allowing for easier secret setting.
"""

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


def get_provider_config_override(id: str, app=current_app) -> dict:
    """Get the config override dict for a provider by ID, or an empty dictionary by default."""
    return app.config["VCS_PROVIDER_CONFIG_DICT"].get(id, {})
