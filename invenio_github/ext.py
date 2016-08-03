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

"""Invenio module that adds GitHub integration to the platform."""

from __future__ import absolute_import, print_function

from flask import current_app
from six import string_types
from sqlalchemy import event
from werkzeug.utils import cached_property, import_string

from . import config
from .api import GitHubRelease


class InvenioGitHub(object):
    """Invenio-GitHub extension."""

    def __init__(self, app=None):
        """Extension initialization."""
        if app:
            self.init_app(app)

    @cached_property
    def release_api_class(self):
        """Github Release API class."""
        cls = current_app.config['GITHUB_RELEASE_CLASS']
        if isinstance(cls, string_types):
            cls = import_string(cls)
        assert issubclass(cls, GitHubRelease)
        return cls

    @cached_property
    def record_serializer(self):
        """Github Release API class."""
        imp = current_app.config['GITHUB_RECORD_SERIALIZER']
        if isinstance(imp, string_types):
            return import_string(imp)
        return imp

    def init_app(self, app):
        """Flask application initialization."""
        self.init_config(app)
        app.extensions['invenio-github'] = self

        @app.before_first_request
        def connect_signals():
            """Connect OAuthClient signals."""
            from invenio_oauthclient.models import RemoteAccount
            from invenio_oauthclient.signals import account_setup_committed

            from .api import GitHubAPI
            from .handlers import account_post_init

            account_setup_committed.connect(
                account_post_init,
                sender=GitHubAPI.remote._get_current_object()
            )

            @event.listens_for(RemoteAccount, 'before_delete')
            def receive_before_delete(mapper, connection, target):
                """Listen for the 'before_delete' event."""
                # TODO remove hooks

    def init_config(self, app):
        """Initialize configuration."""
        app.config.setdefault(
            'GITHUB_BASE_TEMPLATE',
            app.config.get('BASE_TEMPLATE',
                           'invenio_github/base.html'))

        app.config.setdefault(
            'GITHUB_SETTINGS_TEMPLATE',
            app.config.get('SETTINGS_TEMPLATE',
                           'invenio_oauth2server/settings/base.html'))

        for k in dir(config):
            if k.startswith('GITHUB_'):
                app.config.setdefault(k, getattr(config, k))
