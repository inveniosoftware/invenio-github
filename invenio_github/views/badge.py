# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2014-2023 CERN.
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


"""DOI Badge Blueprint."""

from __future__ import absolute_import

from flask import Blueprint, abort, current_app, redirect, url_for
from flask_login import current_user

from invenio_github.api import GitHubAPI, GitHubRelease
from invenio_github.models import ReleaseStatus, Repository

blueprint = Blueprint(
    "invenio_github_badge",
    __name__,
    url_prefix="/badge",
    static_folder="../static",
    template_folder="../templates",
)


# Kept for backward compatibility
def get_pid_of_latest_release_or_404(**kwargs):
    """Return PID of the latest release."""
    repo = Repository.query.filter_by(**kwargs).first_or_404()
    release = repo.latest_release(ReleaseStatus.PUBLISHED)
    if release:
        return GitHubRelease(release).pid
    abort(404)


# Kept for backward compatibility
def get_badge_image_url(pid, ext="svg"):
    """Return the badge for a DOI."""
    return url_for(
        "invenio_formatter_badges.badge",
        title=pid.pid_type,
        value=pid.pid_value,
        ext=ext,
    )


# Kept for backward compatibility
def get_doi_url(pid):
    """Return the badge for a DOI."""
    return "https://doi.org/{pid.pid_value}".format(pid=pid)


#
# Views
#
@blueprint.route("/<int:repo_github_id>.svg")
def index(repo_github_id):
    """Generate a badge for a specific GitHub repository."""
    try:
        github_api = GitHubAPI(current_user.id)
        repo = github_api.get_repository(repo_github_id=repo_github_id)
        release = github_api.repo_last_published_release(repo)
        badge_url = url_for(
            "invenio_formatter_badges.badge",
            title=release.badge_title,
            value=release.badge_value,
            ext="svg",
        )
        return redirect(badge_url)
    except Exception as e:
        current_app.logger.error(str(e), exc_info=True)
        abort(404)


# Kept for backward compatibility
@blueprint.route("/<int:user_id>/<path:repo_name>.svg")
def index_old(user_id, repo_name):
    """Generate a badge for a specific GitHub repository."""
    pid = get_pid_of_latest_release_or_404(name=repo_name)
    return redirect(get_badge_image_url(pid))


# Kept for backward compatibility
@blueprint.route("/latestdoi/<int:github_id>")
def latest_doi(github_id):
    """Redirect to the newest record version."""
    pid = get_pid_of_latest_release_or_404(github_id=github_id)
    return redirect(get_doi_url(pid))


# Kept for backward compatibility
@blueprint.route("/latestdoi/<int:user_id>/<path:repo_name>")
def latest_doi_old(user_id, repo_name):
    """Redirect to the newest record version."""
    pid = get_pid_of_latest_release_or_404(name=repo_name)
    return redirect(get_doi_url(pid))
