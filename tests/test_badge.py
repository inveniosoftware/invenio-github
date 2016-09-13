# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015, 2016 CERN.
#
# Invenio is free software: you can redistribute it and/or modify
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

"""Test cases for badge creation."""

from __future__ import absolute_import

from flask import url_for


def test_badge_views(app, release_model):
    """Test create_badge method."""
    with app.test_client() as client:
        badge_url = url_for('invenio_github_badge.index',
                            github_id=release_model.release_id)
        badge_resp = client.get(badge_url)
        assert release_model.record['doi'] in badge_resp.location

    with app.test_client() as client:
        # Test with non-existent github id
        badge_url = url_for('invenio_github_badge.index', github_id=42)
        badge_resp = client.get(badge_url)
        assert badge_resp.status_code == 404
