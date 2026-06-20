# SPDX-FileCopyrightText: 2023 CERN.
# SPDX-License-Identifier: MIT

"""Test cases for badge creation."""

from invenio_github.models import Repository


def test_repository_unbound(app):
    """Test create_badge method."""
    assert Repository(name="org/repo", github_id=1).latest_release() is None
