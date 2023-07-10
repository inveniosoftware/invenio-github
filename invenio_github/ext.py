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

"""Invenio module that adds GitHub integration to the platform."""

from flask import current_app
from six import string_types
from werkzeug.utils import cached_property, import_string

from invenio_github.api import GitHubRelease
from invenio_github.utils import obj_or_import_string

from . import config


class InvenioGitHub(object):
    """Invenio-GitHub extension."""

    def __init__(self, app=None):
        """Extension initialization."""
        if app:
            self.init_app(app)

    @cached_property
    def release_api_class(self):
        """Github Release API class."""
        cls = current_app.config["GITHUB_RELEASE_CLASS"]
        if isinstance(cls, string_types):
            cls = import_string(cls)
        assert issubclass(cls, GitHubRelease)
        return cls

    @cached_property
    def release_error_handlers(self):
        """Github Release error handlers."""
        error_handlers = current_app.config.get("GITHUB_ERROR_HANDLERS") or []
        return [
            (obj_or_import_string(error_cls), obj_or_import_string(handler))
            for error_cls, handler in error_handlers
        ]

    def init_app(self, app):
        """Flask application initialization."""
        self.init_config(app)
        app.extensions["invenio-github"] = self

    def init_config(self, app):
        """Initialize configuration."""
        app.config.setdefault(
            "GITHUB_SETTINGS_TEMPLATE",
            app.config.get("SETTINGS_TEMPLATE", "invenio_github/settings/base.html"),
        )

        for k in dir(config):
            if k.startswith("GITHUB_"):
                app.config.setdefault(k, getattr(config, k))
