# SPDX-FileCopyrightText: 2023 CERN.
# SPDX-License-Identifier: MIT

"""Configuration for GitHub module."""

from datetime import timedelta

GITHUB_WEBHOOK_RECEIVER_ID = "github"
"""Local name of webhook receiver."""

GITHUB_WEBHOOK_RECEIVER_URL = None
"""URL format to be used when creating a webhook on GitHub.

This configuration variable must be set explicitly. Example::

    http://localhost:5000/api/receivers/github/events/?access_token={token}

.. note::

    This config variable is used because using `url_for` to get and external
    url of an `invenio_base.api_bluebrint`, while inside the regular app
    context, doesn't work as expected.
"""

GITHUB_WEBHOOK_SYNC_BATCH_SIZE = 20
"""Number of repositories to be processed in a single batch when syncing hooks.

If the user has more than 20 repositories, multiple tasks will be created,
syncing them in parallel. Thereby the sync process should finish in a timely
manner and we avoid timeouts on platforms like Zenodo.

Decrease this value if you experience task timeouts.
"""

GITHUB_SHARED_SECRET = "CHANGEME"
"""Shared secret between you and GitHub.

Used to make GitHub sign webhook requests with HMAC.

See http://developer.github.com/v3/repos/hooks/#example
"""

GITHUB_INSECURE_SSL = False
"""Determine if the GitHub webhook request will check the SSL certificate.

Never set to True in a production environment, but can be useful for
development and integration servers.
"""

GITHUB_REFRESH_TIMEDELTA = timedelta(days=1)
"""Time period after which a GitHub account sync should be initiated."""

GITHUB_RELEASE_CLASS = "invenio_github.api:GitHubRelease"
"""GitHubRelease class to be used for release handling."""

GITHUB_TEMPLATE_INDEX = "invenio_github/settings/index.html"
"""Repositories list template."""

GITHUB_TEMPLATE_VIEW = "invenio_github/settings/view.html"
"""Repository detail view template."""

GITHUB_ERROR_HANDLERS = None
"""Definition of the way specific exceptions are handled."""

GITHUB_MAX_CONTRIBUTORS_NUMBER = 30
"""Max number of contributors of a release to be retrieved from Github."""

GITHUB_INTEGRATION_ENABLED = False
"""Enables the github integration."""

GITHUB_CITATION_FILE = None
"""Citation file name."""

GITHUB_CITATION_METADATA_SCHEMA = None
"""Citation metadata schema."""

GITHUB_ZIPBALL_TIMEOUT = 300
"""Timeout for the zipball download, in seconds."""
