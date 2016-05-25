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

"""Upload release as deposit."""

import json

import requests
from flask import current_app, url_for


class InvenioGitHubAPIException(Exception):
    """General GitHub API Exception."""


class InvenioGitHubAPIWarning(InvenioGitHubAPIException):
    """Warning from GitHub API."""


class InvenioGitHubAPIError(InvenioGitHubAPIException):
    """Indicate GitHub API error."""


def requests_request_factory(method, endpoint, urlargs, data, is_json, headers,
                             files, verify_ssl):
    """Make requests with request package."""
    client_func = getattr(requests, method.lower())

    if headers is None:
        headers = [('Content-Type', 'application/json')] if is_json else []

    if data is not None:
        request_args = dict(
            data=json.dumps(data) if is_json else data,
            headers=dict(headers),
        )
    else:
        request_args = {}

    if files is not None:
        request_args['files'] = files

    return client_func(
        url_for(
            endpoint,
            _external=True,
            _scheme='https',
            **urlargs
        ),
        verify=verify_ssl,
        **request_args
    )


class DepositClient(object):
    """Client for uploading software release using deposit API."""

    def __init__(self, access_token, ssl_verify=True, request_factory=None):
        """Configure deposit client."""
        self.access_token = access_token
        self.ssl_verify = ssl_verify
        self.request_factory = request_factory or current_app.extensions.get(
            'invenio_github.request_factory', requests_request_factory)

    def make_request(self, method, endpoint, urlargs={}, data=None,
                     is_json=True, headers=None, files=None):
        """Prepare request to deposit API."""
        urlargs['access_token'] = self.access_token

        return self.request_factory(
            method, endpoint, urlargs, data, is_json, headers, files,
            self.ssl_verify
        )

    def get(self, *args, **kwargs):
        """GET request."""
        return self.make_request('get', *args, **kwargs)

    def post(self, *args, **kwargs):
        """POST request."""
        return self.make_request('post', *args, **kwargs)

    def put(self, *args, **kwargs):
        """PUT request."""
        return self.make_request('put', *args, **kwargs)

    def delete(self, *args, **kwargs):
        """DELETE request."""
        return self.make_request('delete', *args, **kwargs)


def upload(access_token, metadata, files, publish=False, request_factory=None):
    """Deposit Upload."""
    client = DepositClient(
        access_token,
        ssl_verify=False,
        request_factory=request_factory,
    )

    # Create deposition
    r = client.post('invenio_deposit_rest.depid_list', data={})
    if r.status_code != 201:
        raise InvenioGitHubAPIError('Could not create deposition.', response=r)

    deposition_id = r.json()['id']

    # Upload a file
    for (zipball_url, filename) in files:
        githubres = requests.get(zipball_url, stream=True)
        if githubres.status_code != 200:
            raise Exception(
                'Could not retrieve archive from GitHub: %s' % zipball_url
            )

        r = client.post(
            'depositionfilelistresource',
            urlargs=dict(resource_id=deposition_id),
            is_json=False,
            data={'filename': filename},
            files={'file': githubres.raw},
        )
        if r.status_code != 201:
            raise InvenioGitHubAPIWarning('Could not add file', deposition_id,
                                          response=r)

    # Set metadata (being set here to ensure file is fetched)
    r = client.put(
        'depositionresource',
        urlargs=dict(resource_id=deposition_id),
        data={'metadata': metadata}
    )
    if r.status_code != 200:
        errors = {}
        if r.status_code == 400:
            errors = r.json()
        raise InvenioGitHubAPIWarning(
            'Problem with metadata', deposition_id, errors,
            response=r, metadata=metadata
        )

    if publish:
        r = client.post(
            'depositionactionresource',
            urlargs=dict(resource_id=deposition_id, action_id='publish'),
        )
        if r.status_code != 202:
            raise InvenioGitHubAPIWarning('Could not publish deposition',
                                          deposition_id, response=r)

        return r.json()
    else:
        r = client.get(
            'depositionresource',
            urlargs=dict(resource_id=deposition_id),
        )
        if r.status_code != 200:
            raise InvenioGitHubAPIWarning('Could not get deposition',
                                          deposition_id, response=r)
        return r.json()
