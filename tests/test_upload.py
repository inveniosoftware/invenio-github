# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2014, 2015, 2016 CERN.
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

from __future__ import absolute_import

import binascii
from functools import partial

from invenio_db import db
from six import BytesIO

from invenio_github.upload import upload


def make_file_fixture(filename, content):
    """Generate a file fixture suitable for use with the Flask test client."""
    fp = BytesIO(content)
    return fp, filename


def FIXME_test_upload(app, db, tester_id, deposit_token, request_factory):
    metadata = dict(
        upload_type="software",
        title="Test title",
        creators=[
            dict(name="Doe, John", affiliation="Atlantis"),
            dict(name="Smith, Jane", affiliation="Atlantis")
        ],
        description="Test Description",
        publication_date="2013-05-08",
    )
    files = [make_file_fixture('test.pdf', b'upload test')]

    metadata = upload(
        deposit_token,
        metadata,
        files,
        publish=True,
        request_factory=request_factory
    )
    assert 'record_id' in metadata
    assert 'doi' in metadata
