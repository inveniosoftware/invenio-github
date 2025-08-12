# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2014, 2015, 2016 CERN.
# Copyright (C) 2024 Graz University of Technology.
# Copyright (C) 2024 KTH Royal Institute of Technology.
#
# Invenio is free software; you can redistribute it and/or modify
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

"""GitHub blueprint for Invenio platform."""

from functools import wraps

from flask import Blueprint, abort, current_app, render_template
from flask_login import current_user, login_required
from invenio_db import db
from invenio_i18n import gettext as _
from sqlalchemy.orm.exc import NoResultFound

from invenio_vcs.api import GitHubAPI
from invenio_vcs.providers import get_provider_by_id
from invenio_vcs.service import VersionControlService

from ..errors import GithubTokenNotFound, RepositoryAccessError, RepositoryNotFoundError


def request_session_token():
    """Requests an oauth session token to be configured for the user."""

    def decorator(f):
        @wraps(f)
        def inner(*args, **kwargs):
            provider = kwargs["provider"]
            svc = VersionControlService(provider, current_user.id)
            if svc.is_authenticated:
                return f(*args, **kwargs)
            raise GithubTokenNotFound(
                current_user, _("VCS provider session token is required")
            )

        return inner

    return decorator


def create_ui_blueprint(app):
    """Creates blueprint and registers UI endpoints if the integration is enabled."""
    blueprint = Blueprint(
        "invenio_github",
        __name__,
        static_folder="../static",
        template_folder="../templates",
        url_prefix="/account/settings/<path:provider>",
    )
    if app.config.get("GITHUB_INTEGRATION_ENABLED", False):
        with app.app_context():  # Todo: Temporary fix, it should be removed when inveniosoftware/invenio-theme#355 is merged
            register_ui_routes(blueprint)
    return blueprint


def create_api_blueprint(app):
    """Creates blueprint and registers API endpoints if the integration is enabled."""
    blueprint_api = Blueprint(
        "invenio_github_api", __name__, url_prefix="/user/vcs/<path:provider>"
    )
    if app.config.get("GITHUB_INTEGRATION_ENABLED", False):
        register_api_routes(blueprint_api)
    return blueprint_api


def register_ui_routes(blueprint):
    """Register ui routes."""

    @blueprint.route("/")
    @login_required
    def get_repositories(provider):
        """Display list of the user's repositories."""
        svc = VersionControlService(provider, current_user.id)
        ctx = dict(connected=False)
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

        return render_template(current_app.config["GITHUB_TEMPLATE_INDEX"], **ctx)

    @blueprint.route("/repository/<path:repo_id>")
    @login_required
    @request_session_token()
    def get_repository(provider, repo_id):
        """Displays one repository.

        Retrieves and builds context to display all repository releases, if any.
        """
        svc = VersionControlService(provider, current_user.id)

        try:
            repo = svc.get_repository(repo_id)
            latest_release = svc.get_repo_latest_release(repo)
            default_branch = svc.get_repo_default_branch(repo_id)
            releases = svc.list_repo_releases(repo)
            return render_template(
                current_app.config["GITHUB_TEMPLATE_VIEW"],
                latest_release=latest_release,
                repo=repo,
                releases=releases,
                default_branch=default_branch,
            )
        except RepositoryAccessError:
            abort(403)
        except (NoResultFound, RepositoryNotFoundError):
            abort(404)
        except Exception as exc:
            current_app.logger.exception(str(exc))
            abort(400)


def register_api_routes(blueprint):
    """Register API routes."""

    @login_required
    @request_session_token()
    @blueprint.route("/repositories/sync", methods=["POST"])
    def sync_user_repositories(provider):
        """Synchronizes user repos.

        Currently:
            POST /api/user/github/repositories/sync
        Previously:
            POST /account/settings/github/hook
        """
        try:
            svc = VersionControlService(provider, current_user.id)
            svc.sync(async_hooks=False)
            db.session.commit()
        except Exception as exc:
            current_app.logger.exception(str(exc))
            abort(400)

        return "", 200

    @login_required
    @request_session_token()
    @blueprint.route("/", methods=["POST"])
    def init_user_github(provider):
        """Initialises github account for an user."""
        try:
            svc = VersionControlService(provider, current_user.id)
            svc.init_account()
            svc.sync(async_hooks=False)
            db.session.commit()
        except Exception as exc:
            current_app.logger.exception(str(exc))
            abort(400)
        return "", 200

    @login_required
    @request_session_token()
    @blueprint.route("/repositories/<repository_id>/enable", methods=["POST"])
    def enable_repository(provider, repository_id):
        """Enables one repository.

        Currently:
            POST /api/user/github/repositories/<repository_id>/enable
        Previously:
            POST /account/settings/github/hook
        """
        try:
            svc = VersionControlService(provider, current_user.id)
            create_success = svc.enable_repository(repository_id)

            db.session.commit()
            if create_success:
                return "", 201
            else:
                raise Exception(
                    _("Failed to enable repository, hook creation not successful.")
                )
        except RepositoryAccessError:
            abort(403)
        except RepositoryNotFoundError:
            abort(404)
        except Exception as exc:
            current_app.logger.exception(str(exc))
            abort(400)

    @login_required
    @request_session_token()
    @blueprint.route("/repositories/<repository_id>/disable", methods=["POST"])
    def disable_repository(provider, repository_id):
        """Disables one repository.

        Currently:
            POST /api/user/github/repositories/<repository_id>/disable
        Previously:
            DELETE /account/settings/github/hook
        """
        try:
            svc = VersionControlService(provider, current_user.id)
            remove_success = svc.disable_repository(repository_id)

            db.session.commit()
            if remove_success:
                return "", 204
            else:
                raise Exception(
                    _("Failed to disable repository, hook removal not successful.")
                )
        except RepositoryNotFoundError:
            abort(404)
        except RepositoryAccessError:
            abort(403)
        except Exception as exc:
            current_app.logger.exception(str(exc))
            abort(400)
