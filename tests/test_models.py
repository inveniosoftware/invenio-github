# -*- coding: utf-8 -*-
#
# Copyright (C) 2023-2025 CERN.
#
# Invenio-VCS is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
"""Test cases for VCS models."""

from invenio_vcs.models import Repository


def test_repository_unbound(app):
    """Test unbound repository."""
    assert (
        Repository(
            full_name="org/repo", provider_id="1", provider="test"
        ).latest_release()
        is None
    )
