# -*- coding: utf-8 -*-
# This file is part of Invenio.
# Copyright (C) 2014-2025 CERN.
# Copyright (C) 2024 Graz University of Technology.
# Copyright (C) 2024 KTH Royal Institute of Technology.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""VCS views blueprint for Invenio platform."""

from functools import wraps

from flask import Blueprint, abort, current_app, render_template
from flask_login import current_user, login_required
from invenio_db import db
from invenio_i18n import gettext as _
from sqlalchemy.orm.exc import NoResultFound

from invenio_vcs.service import VCSService

from ..errors import RepositoryAccessError, RepositoryNotFoundError, VCSTokenNotFound


def vcs_error_handler():
    """Common error handling behaviour for VCS routes."""

    def decorator(f):
        @wraps(f)
        def inner(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except RepositoryAccessError:
                abort(403)
            except (NoResultFound, RepositoryNotFoundError):
                abort(404)
            except Exception as exc:
                current_app.logger.exception(str(exc))
                abort(400)

        return inner

    return decorator


def require_vcs_connected():
    """Requests an oauth session token to be configured for the user."""

    def decorator(f):
        @wraps(f)
        def inner(*args, **kwargs):
            provider = kwargs["provider"]
            svc = VCSService.for_provider_and_user(provider, current_user.id)
            if svc.is_authenticated:
                return f(*args, **kwargs)
            raise VCSTokenNotFound(
                current_user, _("Account must be connected to the VCS provider.")
            )

        return inner

    return decorator


def create_ui_blueprint(app):
    """Creates blueprint and registers UI endpoints if the integration is enabled."""
    blueprint = Blueprint(
        "invenio_vcs",
        __name__,
        static_folder="../static",
        template_folder="../templates",
        url_prefix="/account/settings/vcs/<provider>",
    )
    with app.app_context():  # Todo: Temporary fix, it should be removed when inveniosoftware/invenio-theme#355 is merged
        register_ui_routes(blueprint)
    return blueprint


def create_api_blueprint(app):
    """Creates blueprint and registers API endpoints if the integration is enabled."""
    blueprint_api = Blueprint(
        "invenio_vcs_api", __name__, url_prefix="/user/vcs/<provider>"
    )
    register_api_routes(blueprint_api)
    return blueprint_api


def register_ui_routes(blueprint):
    """Register ui routes."""

    @blueprint.route("/")
    @login_required
    @vcs_error_handler()
    def get_repositories(provider):
        """Display list of the user's repositories."""
        svc = VCSService.for_provider_and_user(provider, current_user.id)
        ctx: dict = dict(
            connected=False,
            provider=provider,
            vocabulary=svc.provider.factory.vocabulary,
            repo_url=svc.provider.factory.url_for_repository,
            new_repo_url=svc.provider.factory.url_for_new_repo(),
        )

        if svc.is_authenticated:
            # Generate the repositories view object
            repos = svc.list_repositories()
            last_sync = svc.get_last_sync_time()

            ctx.update(
                {
                    "connected": True,
                    "repos": repos,
                    "last_sync": last_sync,
                }
            )

        return render_template(current_app.config["VCS_TEMPLATE_INDEX"], **ctx)

    @blueprint.route("/repository/<path:repo_id>")
    @login_required
    @require_vcs_connected()
    @vcs_error_handler()
    def get_repository(provider, repo_id):
        """Displays one repository.

        Retrieves and builds context to display all repository releases, if any.
        """
        svc = VCSService.for_provider_and_user(provider, current_user.id)

        repo = svc.get_repository(repo_id)
        latest_release = svc.get_repo_latest_release(repo)
        default_branch = svc.get_repo_default_branch(repo_id)
        releases = svc.list_repo_releases(repo)
        release_url = svc.provider.factory.url_for_release
        new_release_url = svc.provider.factory.url_for_new_release(repo.full_name)
        new_citation_file_url = svc.provider.factory.url_for_new_file(
            repo.full_name, default_branch or "main", "CITATION.cff"
        )

        return render_template(
            current_app.config["VCS_TEMPLATE_VIEW"],
            latest_release=latest_release,
            provider=provider,
            repo=repo,
            releases=releases,
            default_branch=default_branch,
            release_url=release_url,
            new_release_url=new_release_url,
            new_citation_file_url=new_citation_file_url,
            vocabulary=svc.provider.factory.vocabulary,
        )


def register_api_routes(blueprint):
    """Register API routes."""

    @login_required
    @require_vcs_connected()
    @vcs_error_handler()
    @blueprint.route("/repositories/sync", methods=["POST"])
    def sync_user_repositories(provider):
        """Synchronizes user repos.

        Currently:
            POST /api/user/vcs/<provider>/repositories/sync
        Previously:
            POST /account/settings/github/hook
        """
        svc = VCSService.for_provider_and_user(provider, current_user.id)
        svc.sync()
        db.session.commit()

        return "", 200

    @login_required
    @require_vcs_connected()
    @vcs_error_handler()
    @blueprint.route("/repositories/<repository_id>/enable", methods=["POST"])
    def enable_repository(provider, repository_id):
        """Enables one repository.

        Currently:
            POST /api/user/vcs/<provider>/repositories/<repository_id>/enable
        Previously:
            POST /account/settings/github/hook
        """
        svc = VCSService.for_provider_and_user(provider, current_user.id)
        create_success = svc.enable_repository(repository_id)

        db.session.commit()
        if create_success:
            return "", 201
        else:
            raise Exception(
                _("Failed to enable repository, hook creation not successful.")
            )

    @login_required
    @require_vcs_connected()
    @vcs_error_handler()
    @blueprint.route("/repositories/<repository_id>/disable", methods=["POST"])
    def disable_repository(provider, repository_id):
        """Disables one repository.

        Currently:
            POST /api/user/vcs/<provider>/repositories/<repository_id>/disable
        Previously:
            DELETE /account/settings/github/hook
        """
        svc = VCSService.for_provider_and_user(provider, current_user.id)
        remove_success = svc.disable_repository(repository_id)

        db.session.commit()
        if remove_success:
            return "", 204
        else:
            raise Exception(
                _("Failed to disable repository, hook removal not successful.")
            )
