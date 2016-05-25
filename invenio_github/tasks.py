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

import sys

import requests
import six
from celery import shared_task
from celery.utils.log import get_task_logger
from flask import current_app
from invenio_db import db
from invenio_oauth2server.models import Token as ProviderToken
from invenio_oauthclient.proxies import current_oauthclient
from invenio_webhooks.models import Event

from .helpers import get_account, get_api
from .upload import upload
from .utils import get_contributors, get_extra_metadata, get_owner, init_api, \
    is_valid_sender, remove_hook, revoke_token, submitted_deposition

logger = get_task_logger(__name__)


@shared_task(ignore_result=True)
def disconnect_github(remote_app, access_token, extra_data):
    """Uninstall webhooks."""
    # Note at this point the remote account and all associated data have
    # already been deleted. The celery task is passed the access_token and
    # extra_data to make some last cleanup and afterwards delete itself
    # remotely.
    remote = current_oauthclient.remote_apps[remote_app]

    try:
        gh = init_api(access_token)

        # Remove all installed hooks.
        for full_name, repo in six.iteritems(extra_data["repos"]):
            if repo.get('hook', None):
                remove_hook(gh, extra_data, full_name)
    finally:
        revoke_token(remote, access_token)


@shared_task(ignore_result=True)
def handle_github_payload(event, verify_sender=True):
    """Handle incoming notification from GitHub on a new release."""
    # Ping event
    if 'hook_id' in event.payload and 'zen' in event.payload:
        # TODO: record we sucessfully received ping event
        return

    # Get account and internal access token
    account = get_account(user_id=event.user_id)
    gh = get_api(user_id=event.user_id)
    access_token = ProviderToken.query.filter_by(
        id=account.extra_data["tokens"]["internal"]
    ).first().access_token

    # Validate payload sender
    if verify_sender and \
       not is_valid_sender(account.extra_data, event.payload):
        raise Exception("Invalid sender for payload %s for user %s" % (
            event.payload, event.user_id
        ))

    try:
        # Extra metadata from .zenodo.json and github repository
        metadata = extract_metadata(gh, event.payload)

        # Extract zip snapshot from github
        files = extract_files(event.payload, account.tokens[0].access_token)

        # Upload into Zenodo
        deposition = upload(access_token, metadata, files, publish=True)

        # TODO: Add step to update metadata of all previous records
        submitted_deposition(
            account.extra_data, event.payload['repository']['full_name'],
            deposition, event.payload['release']['tag_name']
        )
        account.extra_data.changed()
        db.session.commit()
        # Send email to user that release was included.
    except Exception as e:
        # Handle errors and possibly send user an email
        # Send email to user
        current_app.logger.exception("Failed handling GitHub payload")
        db.session.commit()
        six.reraise(*sys.exc_info())


def extract_title(release, repository):
    """Extract title from a release."""
    if release['name']:
        return "%s: %s" % (repository['name'], release['name'])
    else:
        return "%s %s" % (repository['name'], release['tag_name'])


def extract_description(gh, release, repository):
    """Extract description from a release."""
    return gh.markdown(release['body']) or repository['description'] or \
        'No description provided.'


def extract_metadata(gh, payload):
    """Extract metadata from a release."""
    # TODO make the serializer configurable.
    release = payload["release"]
    repository = payload["repository"]

    defaults = dict(
        upload_type='software',
        publication_date=release['published_at'][:10],
        title=extract_title(release, repository),
        description=extract_description(gh, release, repository),
        access_right='open',
        license='other-open',
        related_identifiers=[],
    )

    # Extract metadata form .zenodo.json
    metadata = get_extra_metadata(
        gh, repository['owner']['login'], repository['name'],
        release['tag_name']
    )

    if metadata is not None:
        defaults.update(metadata)

    # Remove some fields
    for field in ['prereserve_doi', 'doi']:
        defaults.pop(field, None)

    # Add link to GitHub in related identifiers
    if 'related_identifiers' not in defaults:
        defaults['related_identifiers'] = []

    defaults['related_identifiers'].append({
        'identifier': 'https://github.com/%s/tree/%s' % (
            repository['full_name'], release['tag_name']
        ),
        'relation': 'isSupplementTo'
    })

    # Add creators if not specified
    if 'creators' not in defaults:
        defaults['creators'] = get_contributors(
            gh, repository['owner']['login'], repository['name'],
        )
        if not defaults['creators']:
            defaults['creators'] = get_owner(gh, repository['owner']['login'])
        if not defaults['creators']:
            defaults['creators'] = [dict(name='UNKNOWN', affliation='')]

    return defaults


def extract_files(payload, access_token):
    """Extract files to download from GitHub payload."""
    release = payload["release"]
    repository = payload["repository"]

    tag_name = release["tag_name"]
    repo_name = repository["name"]

    zipball_url = release["zipball_url"]
    filename = "%(repo_name)s-%(tag_name)s.zip" % {
        "repo_name": repo_name, "tag_name": tag_name
    }

    zipball_url = zipball_url + "?access_token={0}".format(access_token)

    # Check if zipball exists.
    r = requests.head(zipball_url)
    if r.status_code != 302:
        raise Exception(
            "Could not retrieve archive from GitHub: %s" % zipball_url
        )

    return [(zipball_url, filename)]
