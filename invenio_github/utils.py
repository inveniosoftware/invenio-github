# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2014, 2015, 2016 CERN.
#
# Invenio is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""Various utility functions."""

import json
from datetime import datetime
from operator import itemgetter

import dateutil.parser
import pytz
import requests
from flask import current_app


def utcnow():
    """UTC timestamp (with timezone)."""
    return datetime.now(tz=pytz.utc)


def iso_utcnow():
    """UTC ISO8601 formatted timestamp."""
    return utcnow().isoformat()


def parse_timestamp(x):
    """Parse ISO8601 formatted timestamp."""
    dt = dateutil.parser.parse(x)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.utc)
    return dt


def get_extra_metadata(gh, owner, repo_name, ref):
    """Get the metadata file."""
    try:
        content = gh.repository(owner, repo_name).contents(
            current_app.config['GITHUB_METADATA_FILE'], ref=ref
        )
        if not content:
            # File does not exists in the given ref
            return None
        return json.loads(content.decoded)
    except Exception:
        current_app.logger.exception('Failed to decode {0}.'.format(
            current_app.config['GITHUB_METADATA_FILE']
        ))
        # Problems decoding the file
        return None


def get_owner(gh, owner):
    """Get owner of repository as a creator."""
    try:
        u = gh.user(owner)
        name = u.name or u.login
        company = u.company or ''
        return [dict(name=name, affliation=company)]
    except Exception:
        current_app.logger.exception('Failed to get GitHub owner')
        return None


def get_contributors(gh, owner, repo_name):
    """Get list of contributors to a repository."""
    try:
        contrib_url = gh.repository(owner, repo_name).contributors_url

        r = requests.get(contrib_url)
        if r.status_code == 200:
            contributors = r.json()

            def get_author(contributor):
                r = requests.get(contributor['url'])
                if r.status_code == 200:
                    data = r.json()
                    return dict(
                        name=(data['name'] if 'name' in data and data['name']
                              else data['login']),
                        affiliation=(data['company'] if 'company' in data
                                     else ''),
                    )

            # Sort according to number of contributions
            contributors.sort(key=itemgetter('contributions'))
            contributors = [get_author(x) for x in reversed(contributors)
                            if x['type'] == 'User']
            contributors = filter(lambda x: x is not None, contributors)

            return contributors
    except Exception:
        current_app.logger.exception('Failed to get GitHub contributors.')
        return None


def is_valid_token(remote, access_token):
    """Check validity of a GitHub access token.

    GitHub requires the use of Basic Auth to query token validity.
    200 - valid token
    404 - invalid token
    """
    r = requests.get(
        '%(base)s/applications/%(client_id)s/tokens/%(access_token)s' % {
            'client_id': remote.consumer_key,
            'access_token': access_token,
            'base': current_app.config['GITHUB_BASE_URL']
        },
        auth=(remote.consumer_key, remote.consumer_secret)
    )

    return r.status_code == 200


def revoke_token(remote, access_token):
    """Revoke an access token."""
    r = requests.delete(
        '%(base)s/applications/%(client_id)s/tokens/%(access_token)s' % {
            'client_id': remote.consumer_key,
            'access_token': access_token,
            'base': current_app.config['GITHUB_BASE_URL']
        },
        auth=(remote.consumer_key, remote.consumer_secret)
    )

    return r.status_code == 200


def is_valid_sender(extra_data, payload):
    """Check if the sender is valid."""
    return payload['repository']['full_name'] in extra_data['repos']
