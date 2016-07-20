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


"""DOI Badge Blueprint."""

from __future__ import absolute_import

from flask import Blueprint, abort, redirect, url_for

from ..models import Repository

blueprint = Blueprint(
    'invenio_github_badge',
    __name__,
    url_prefix='/badge',
    static_folder='../static',
    template_folder='../templates',
)


def get_badge_url(doi):
    """Return the svg badge for a DOI."""
    return url_for('invenio_formatter_badges.badge', title='doi', value=doi,
                   ext='svg')


#
# Views
#
@blueprint.route('/<int:github_id>.svg')
def index(github_id):
    """Generate a badge for a specific GitHub repository."""
    repo = Repository.query.filter_by(github_id=github_id).first()
    if repo and repo.latest_release and repo.latest_release.doi:
        return redirect(get_badge_url(repo.latest_release.doi))
    return abort(404)


@blueprint.route('/<int:user_id>/<path:repo_name>.svg')
def index_old(user_id, repo_name):
    """Generate a badge for a specific GitHub repository."""
    repo = Repository.query.filter_by(name=repo_name).first()
    if repo and repo.latest_release and repo.latest_release.doi:
        return redirect(get_badge_url(repo.latest_release.doi))
    return abort(404)


@blueprint.route('/latestdoi/<int:github_id>')
def latest_doi(github_id):
    """Redirect to the newest record version."""
    repo = Repository.query.filter_by(github_id=github_id).first()
    if repo and repo.latest_release and repo.latest_release.doi:
        return redirect('http://doi.org/{doi}'.format(
            doi=repo.latest_release.doi))
    return abort(404)


@blueprint.route('/latestdoi/<int:user_id>/<path:repo_name>')
def latest_doi_old(user_id, repo_name):
    """Redirect to the newest record version."""
    repo = Repository.query.filter_by(name=repo_name).first()
    if repo and repo.latest_release and repo.latest_release.doi:
        return redirect('http://doi.org/{doi}'.format(
            doi=repo.latest_release.doi))
    return abort(404)
