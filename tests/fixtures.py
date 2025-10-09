# -*- coding: utf-8 -*-
#
# Copyright (C) 2023-2025 CERN.
#
# Invenio-VCS is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
"""Define fixtures for tests."""

from invenio_vcs.models import ReleaseStatus
from invenio_vcs.service import VCSRelease


class TestVCSRelease(VCSRelease):
    """Implements VCSRelease with test methods."""

    def publish(self):
        """Sets release status to published.

        Does not create a "real" record, as this only used to test the API.
        """
        self.db_release.status = ReleaseStatus.PUBLISHED
        self.db_release.record_id = "445aaacd-9de1-41ab-af52-25ab6cb93df7"
        return {}

    def process_release(self):
        """Processes a release."""
        self.publish()
        return {}

    def resolve_record(self):
        """Resolves a record.

        Returns an empty object as this class is only used to test the API.
        """
        return {}

    @property
    def badge_title(self):
        """Test title for the badge."""
        return "DOI"

    @property
    def badge_value(self):
        """Test value for the badge."""
        return self.db_release.tag
