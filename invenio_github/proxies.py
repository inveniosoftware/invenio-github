# SPDX-FileCopyrightText: 2023 CERN.
# SPDX-License-Identifier: MIT

"""Proxy for current previewer."""

from flask import current_app
from werkzeug.local import LocalProxy

current_github = LocalProxy(lambda: current_app.extensions["invenio-github"])
