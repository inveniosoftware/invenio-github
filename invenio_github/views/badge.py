# SPDX-FileCopyrightText: 2014-2023 CERN.
# SPDX-License-Identifier: MIT

"""DOI Badge Blueprint."""

from __future__ import absolute_import

from flask import Blueprint, abort, current_app, redirect, url_for
from flask_login import current_user

from invenio_github.api import GitHubAPI
from invenio_github.errors import ReleaseNotFound
from invenio_github.models import ReleaseStatus, Repository
from invenio_github.proxies import current_github

blueprint = Blueprint(
    "invenio_github_badge",
    __name__,
    url_prefix="/badge",
    static_folder="../static",
    template_folder="../templates",
)


#
# Views
#
@blueprint.route("/<int:repo_github_id>.svg")
def index(repo_github_id):
    """Generate a badge for a specific GitHub repository (by github ID)."""
    repo = Repository.query.filter(Repository.github_id == repo_github_id).one_or_none()
    if not repo:
        abort(404)

    latest_release = repo.latest_release(ReleaseStatus.PUBLISHED)
    if not latest_release:
        abort(404)

    release = current_github.release_api_class(latest_release)
    # release.badge_title points to "DOI"
    # release.badge_value points to the record "pids.doi.identifier"
    badge_url = url_for(
        "invenio_formatter_badges.badge",
        title=release.badge_title,
        value=release.badge_value,
        ext="svg",
    )
    return redirect(badge_url)


# Kept for backward compatibility
@blueprint.route("/<int:user_id>/<path:repo_name>.svg")
def index_old(user_id, repo_name):
    """Generate a badge for a specific GitHub repository (by name)."""
    repo = Repository.query.filter(Repository.name == repo_name).one_or_none()
    if not repo:
        abort(404)

    latest_release = repo.latest_release(ReleaseStatus.PUBLISHED)
    if not latest_release:
        abort(404)

    release = current_github.release_api_class(latest_release)
    # release.badge_title points to "DOI"
    # release.badge_value points to the record "pids.doi.identifier"
    badge_url = url_for(
        "invenio_formatter_badges.badge",
        title=release.badge_title,
        value=release.badge_value,
        ext="svg",
    )
    return redirect(badge_url)


# Kept for backward compatibility
@blueprint.route("/latestdoi/<int:github_id>")
def latest_doi(github_id):
    """Redirect to the newest record version."""
    # Without user_id, we can't use GitHubAPI. Therefore, we fetch the latest release using the Repository model directly.
    repo = Repository.query.filter(Repository.github_id == github_id).one_or_none()
    if not repo:
        abort(404)

    latest_release = repo.latest_release(ReleaseStatus.PUBLISHED)
    if not latest_release:
        abort(404)

    release = current_github.release_api_class(latest_release)

    # record.url points to DOI url or HTML url if Datacite is not enabled.
    return redirect(release.record_url)


# Kept for backward compatibility
@blueprint.route("/latestdoi/<int:user_id>/<path:repo_name>")
def latest_doi_old(user_id, repo_name):
    """Redirect to the newest record version."""
    github_api = GitHubAPI(user_id)
    repo = github_api.get_repository(repo_name=repo_name)
    release = github_api.repo_last_published_release(repo)
    if not release:
        abort(404)

    # record.url points to DOI url or HTML url if Datacite is not enabled.
    return redirect(release.record_url)
