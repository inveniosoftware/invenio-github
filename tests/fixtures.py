# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2023 CERN.
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

"""Define fixtures for tests."""
from invenio_vcs.models import ReleaseStatus
from invenio_vcs.service import VCSRelease


class TestVCSRelease(VCSRelease):
    """Implements GithubRelease with test methods."""

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
