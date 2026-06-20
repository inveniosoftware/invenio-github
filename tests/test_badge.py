# SPDX-FileCopyrightText: 2015, 2016 CERN.
# SPDX-License-Identifier: MIT

"""Test cases for badge creation."""

from __future__ import absolute_import

from flask import url_for

# TODO uncomment when migrated
# def test_badge_views(app, release_model):
#     """Test create_badge method."""
#     with app.test_client() as client:
#         badge_url = url_for(
#             "invenio_github_badge.index", github_id=release_model.release_id
#         )
#         badge_resp = client.get(badge_url)
#         assert release_model.record["doi"] in badge_resp.location

#     with app.test_client() as client:
#         # Test with non-existent github id
#         badge_url = url_for("invenio_github_badge.index", github_id=42)
#         badge_resp = client.get(badge_url)
#         assert badge_resp.status_code == 404
