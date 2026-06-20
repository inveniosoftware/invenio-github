# SPDX-FileCopyrightText: 2023 CERN.
# SPDX-License-Identifier: MIT

"""Module tests."""

from flask import Flask

from invenio_github import InvenioGitHub


def test_version():
    """Test version import."""
    from invenio_github import __version__

    assert __version__


def test_init():
    """Test extension initialization."""
    app = Flask("testapp")
    ext = InvenioGitHub(app)
    assert "invenio-github" in app.extensions

    app = Flask("testapp")
    ext = InvenioGitHub()
    assert "invenio-github" not in app.extensions
    ext.init_app(app)
    assert "invenio-github" in app.extensions
