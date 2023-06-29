# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2014, 2015, 2016 CERN.
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
from flask_breadcrumbs import register_breadcrumb
from flask_login import current_user, login_required
from flask_menu import register_menu
from invenio_db import db
from invenio_i18n import gettext as _
from invenio_theme.proxies import current_theme_icons
from speaklater import make_lazy_string
from sqlalchemy.orm.exc import NoResultFound

from invenio_github.api import GitHubAPI
from invenio_github.proxies import current_github

from ..errors import GithubTokenNotFound, RepositoryAccessError


def request_session_token():
    """Requests an oauth session token to be configured for the user."""

    def decorator(f):
        @wraps(f)
        def inner(*args, **kwargs):
            github = GitHubAPI(user_id=current_user.id)
            token = github.session_token
            if token:
                return f(*args, **kwargs)
            raise GithubTokenNotFound(current_user, "Github session token is requested")

        return inner

    return decorator


blueprint = Blueprint(
    "invenio_github",
    __name__,
    static_folder="../static",
    template_folder="../templates",
    url_prefix="/account/settings/github",
)


@blueprint.route("/")
@login_required
@request_session_token()
@register_menu(  # TODO modify?
    blueprint,
    "settings.github",
    # TODO substitute github for icon + 'Github'
    _("Github"),
    # _(
    #     "%(icon)s GitHub",
    #     icon=make_lazy_string(
    #         lambda: '<i class="{icon}"></i>'.format(
    #             icon=current_theme_icons.github
    #         )  # TODO confirm if icon gets picked
    #     ),
    # ),
    order=10,  # TODO confirm
    # active_when=lambda: request.endpoint.startswith("invenio_github."),
)
@register_breadcrumb(blueprint, "breadcrumbs.settings.github", _("GitHub"))
def get_repositories():
    """Display list of the user's repositories."""
    github = GitHubAPI(user_id=current_user.id)
    ctx = dict(connected=False)

    # Generate the repositories view object
    repos = github.get_user_repositories()
    last_sync = github.get_last_sync_time()

    ctx.update(
        {
            # TODO maybe can be refactored. e.g. have two templates and render the correct one.
            "connected": True,
            "repos": sorted(repos.items(), key=lambda x: x[1]["full_name"]),
            "last_sync": last_sync,
        }
    )

    return render_template(current_app.config["GITHUB_TEMPLATE_INDEX"], **ctx)


@blueprint.route("/repository/<path:repo_name>")
@request_session_token()
def get_repository(repo_name):
    """Displays one repository.

    Retrieves and builds context to display all repository releases, if any.
    """
    user_id = current_user.id
    github = GitHubAPI(user_id=user_id)

    try:
        # NOTE: Here we do not check for repository ownership, since it
        # might have changed even though the user might have made releases
        # in the past.
        repo = github.get_repository(repo_name)
        releases = github.get_repository_releases(repo=repo)
        return render_template(
            current_app.config["GITHUB_TEMPLATE_VIEW"],
            repo=repo,
            releases=releases,
            serializer=current_github.record_serializer,
        )
    except RepositoryAccessError as e:
        abort(403)
    except NoResultFound as e:
        abort(404)


###
# TODO to be moved to its own folder (e.g. separate ui / api)
# /api routes
###

blueprint_api = Blueprint("invenio_github_api", __name__)


@login_required
@blueprint_api.route("/user/github/repositories/sync", methods=["POST"])
def sync_user_repositories():
    """Synchronizes user repos.

    Currently:
        POST /api/user/github/repositories/sync
    Previously:
        POST /account/settings/github/hook
    """
    try:
        github = GitHubAPI(user_id=current_user.id)
        github.sync(async_hooks=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        abort(500)

    return "", 200


@login_required
@request_session_token()
@blueprint_api.route("/user/github/", methods=["POST"])
def init_user_github():
    """Initialises github account for an user."""
    try:
        github = GitHubAPI(user_id=current_user.id)
        github.init_account()
        github.sync(async_hooks=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        abort(500)
    return "", 200


@login_required
@request_session_token()
@blueprint_api.route(
    "/user/github/repositories/<repository_id>/enable", methods=["POST"]
)
def enable_repository(repository_id):
    """Enables one repository.

    Currently:
        POST /api/user/github/repositories/<repository_id>/enable
    Previously:
        POST /account/settings/github/hook
    """
    try:
        github = GitHubAPI(user_id=current_user.id)

        repos = github.account.extra_data["repos"]
        create_success = github.create_hook(
            repository_id, repos[repository_id]["full_name"]
        )
        db.session.commit()
        if create_success:
            return "", 201
        else:
            abort(400)
    except Exception:
        db.session.rollback()
        abort(500)


@login_required
@request_session_token()
@blueprint_api.route(
    "/user/github/repositories/<repository_id>/disable", methods=["POST"]
)
def disable_repository(repository_id):
    """Disables one repository.

    Currently:
        POST /api/user/github/repositories/<repository_id>/disable
    Previously:
        DELETE /account/settings/github/hook
    """
    try:
        github = GitHubAPI(user_id=current_user.id)

        repos = github.account.extra_data.get("repos", [])
        remove_success = False
        if repos:
            remove_success = github.remove_hook(
                repository_id, repos[repository_id]["full_name"]
            )
            db.session.commit()
        if remove_success:
            return "", 204
        else:
            abort(400)
    except Exception:
        db.session.rollback()
        abort(500)
