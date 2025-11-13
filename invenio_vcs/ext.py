# -*- coding: utf-8 -*-
# This file is part of Invenio.
# Copyright (C) 2025 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Invenio module that adds VCS integration to the platform."""

from flask import current_app, request
from flask_menu import current_menu
from invenio_i18n import LazyString
from invenio_i18n import gettext as _
from invenio_theme.proxies import current_theme_icons
from six import string_types
from werkzeug.utils import cached_property, import_string

from invenio_vcs.config import get_provider_config_override, get_provider_list
from invenio_vcs.receivers import VCSReceiver
from invenio_vcs.service import VCSRelease
from invenio_vcs.utils import obj_or_import_string

from . import config


class InvenioVCS(object):
    """Invenio-VCS extension."""

    def __init__(self, app=None):
        """Extension initialization."""
        if app:
            self.init_app(app)

    @cached_property
    def release_api_class(self):
        """Release API class."""
        cls = current_app.config["VCS_RELEASE_CLASS"]
        if isinstance(cls, string_types):
            cls = import_string(cls)
        assert issubclass(cls, VCSRelease)
        return cls

    @cached_property
    def release_error_handlers(self):
        """Release error handlers."""
        error_handlers = current_app.config.get("VCS_ERROR_HANDLERS") or []
        return [
            (obj_or_import_string(error_cls), obj_or_import_string(handler))
            for error_cls, handler in error_handlers
        ]

    def init_app(self, app):
        """Flask application initialization."""
        self.init_config(app)
        self.init_config_overrides(app)
        app.extensions["invenio-vcs"] = self

    def init_config(self, app):
        """Initialize configuration."""
        app.config.setdefault(
            "VCS_SETTINGS_TEMPLATE",
            app.config.get("SETTINGS_TEMPLATE", "invenio_vcs/settings/base.html"),
        )

        for k in dir(config):
            if k.startswith("VCS_"):
                app.config.setdefault(k, getattr(config, k))

    def init_config_overrides(self, app):
        """Update each provider to allow overriding its settings via a dict config variable."""
        providers = get_provider_list(app)
        for provider in providers:
            config_override = get_provider_config_override(provider.id, app)
            provider.update_config_override(config_override)


def finalize_app_ui(app):
    """Finalize app."""
    init_menu(app)
    init_webhooks(app)


def finalize_app_api(app):
    """Finalize app."""
    init_webhooks(app)


def init_menu(app):
    """Init menu."""
    for provider in get_provider_list(app):

        def is_active(current_node):
            return (
                request.endpoint.startswith("invenio_vcs.")
                and request.view_args.get("provider", "") == current_node.name
            )

        current_menu.submenu(f"settings.{provider.id}").register(
            endpoint="invenio_vcs.get_repositories",
            endpoint_arguments_constructor=lambda id=provider.id: {"provider": id},
            text=_(
                "%(icon)s %(provider)s",
                icon=LazyString(
                    lambda: f'<i class="{current_theme_icons[provider.icon]}"></i>'
                ),
                provider=provider.name,
            ),
            order=10,
            active_when=is_active,
        )


def init_webhooks(app):
    """Register the webhook receivers based on the configured VCS providers."""
    state = app.extensions.get("invenio-webhooks")
    if state is not None:
        for provider in get_provider_list(app):
            # Procedurally register the webhook receivers instead of including them as an entry point, since
            # they are defined in the VCS provider config list rather than in the instance's setup.cfg file.
            if provider.id not in state.receivers:
                state.register(provider.id, VCSReceiver)
