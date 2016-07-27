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

from invenio_files_rest.models import Bucket
from invenio_webhooks.models import Event
from mock import patch

from invenio_github.api import GitHubRelease
from invenio_github.models import Release, ReleaseStatus, Repository

from . import fixtures


def test_handle_payload(app, db, location, tester_id, remote_token,
                        github_api):

    from invenio_webhooks.models import Event

    extra_data = remote_token.remote_account.extra_data

    assert '1' in extra_data['repos']
    assert 'repo-1' in extra_data['repos']['1']['full_name']
    assert '2' in extra_data['repos']
    assert 'repo-2' in extra_data['repos']['2']['full_name']

    # Create the repository that will make the release

    with db.session.begin_nested():
        Repository.enable(tester_id, github_id=1, name='repo-1', hook=1234)
        event = Event(
            receiver_id='github',
            user_id=tester_id,
            payload=fixtures.PAYLOAD('auser', 'repo-1', 1)
        )
        db.session.add(event)

    with patch('invenio_deposit.api.Deposit.indexer'):
        event.process()

        repo_1 = Repository.query.filter_by(name='repo-1', github_id=1).first()
        assert repo_1.releases.count() == 1

        release = repo_1.releases.first()
        assert release.status == ReleaseStatus.PUBLISHED
        assert release.errors is None
        assert release.tag == 'v1.0'
        assert release.record is not None
        assert release.record.get('control_number') == '1'
        record_files = release.record.get('_files')
        assert len(record_files) == 1
        assert record_files[0]['size'] > 0

        bucket = Bucket.get(record_files[0]['bucket'])
        assert bucket is not None
        assert len(bucket.objects) == 1
        assert bucket.objects[0].key == 'auser/repo-1-v1.0.zip'


def test_extract_metadata(app, db, tester_id, remote_token, github_api):

    Repository.enable(tester_id, github_id=2, name='repo-2', hook=1234)
    event = Event(
        receiver_id='github',
        user_id=tester_id,
        payload=fixtures.PAYLOAD('auser', 'repo-2', 2, tag='v1.0'),
    )
    release = Release.create(event)
    gh = GitHubRelease(release)
    metadata = gh.metadata

    assert metadata['upload_type'] == 'dataset'
    assert metadata['license'] == 'mit-license'
    assert len(metadata['creators']) == 2
