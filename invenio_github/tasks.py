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

"""Task for managing GitHub integration."""

from __future__ import absolute_import

from celery import shared_task
from invenio_db import db
from invenio_oauthclient.proxies import current_oauthclient

from .utils import revoke_token


@shared_task(ignore_result=True)
def disconnect_github(remote_app, access_token, extra_data):
    """Uninstall webhooks."""
    # Note at this point the remote account and all associated data have
    # already been deleted. The celery task is passed the access_token and
    # extra_data to make some last cleanup and afterwards delete itself
    # remotely.
    from .api import GitHubAPI
    from .models import Repository
    remote = current_oauthclient.remote_apps[remote_app]

    try:
        user_id = access_token.remote_account.user_id
        github = GitHubAPI(user_id=user_id)

        for repo in Repository.query.filter(user_id=user_id):
            if repo.hook:
                github.remove_hook(repo.name)
            repo.user_id = None
    finally:
        revoke_token(remote, access_token)
    db.session.commit()
