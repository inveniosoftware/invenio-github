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

from flask import Blueprint, abort, redirect, url_for
from flask_login import current_user

from invenio_vcs.config import get_provider_by_id
from invenio_vcs.models import ReleaseStatus, Repository
from invenio_vcs.proxies import current_vcs
from invenio_vcs.service import VCSService

blueprint = Blueprint(
    "invenio_vcs_badge",
    __name__,
    url_prefix="/badge/<provider>",
    static_folder="../static",
    template_folder="../templates",
)


@blueprint.route("/<repo_provider_id>.svg")
def index(provider, repo_provider_id):
    """Generate a badge for a specific GitHub repository (by github ID)."""
    repo = Repository.query.filter(
        Repository.provider_id == repo_provider_id, Repository.provider == provider
    ).one_or_none()
    if not repo:
        abort(404)

    latest_release = repo.latest_release(ReleaseStatus.PUBLISHED)
    if not latest_release:
        abort(404)

    provider = get_provider_by_id(provider).for_user(current_user.id)
    release = current_vcs.release_api_class(latest_release, provider)

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
def index_old(provider, user_id, repo_name):
    """Generate a badge for a specific GitHub repository (by name)."""
    repo = Repository.query.filter(
        Repository.name == repo_name, Repository.provider == provider
    ).one_or_none()
    if not repo:
        abort(404)

    latest_release = repo.latest_release(ReleaseStatus.PUBLISHED)
    if not latest_release:
        abort(404)

    provider = get_provider_by_id(provider).for_user(current_user.id)
    release = current_vcs.release_api_class(latest_release, provider)

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
@blueprint.route("/latestdoi/<provider_id>")
def latest_doi(provider, provider_id):
    """Redirect to the newest record version."""
    # Without user_id, we can't use GitHubAPI. Therefore, we fetch the latest release using the Repository model directly.
    repo = Repository.query.filter(
        Repository.provider_id == provider_id, Repository.provider == provider
    ).one_or_none()
    if not repo:
        abort(404)

    latest_release = repo.latest_release(ReleaseStatus.PUBLISHED)
    if not latest_release:
        abort(404)

    provider = get_provider_by_id(provider).for_user(current_user.id)
    release = current_vcs.release_api_class(latest_release, provider)

    # record.url points to DOI url or HTML url if Datacite is not enabled.
    return redirect(release.record_url)


# Kept for backward compatibility
@blueprint.route("/latestdoi/<int:user_id>/<path:repo_name>")
def latest_doi_old(provider, user_id, repo_name):
    """Redirect to the newest record version."""
    svc = VCSService.for_provider_and_user(provider, user_id)
    repo = svc.get_repository(repo_name=repo_name)
    release = svc.get_repo_latest_release(repo)
    if not release:
        abort(404)

    # record.url points to DOI url or HTML url if Datacite is not enabled.
    return redirect(release.record_url)
