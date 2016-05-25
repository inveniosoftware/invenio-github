# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015, 2016 CERN.
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

"""Test cases for badge creation."""

from __future__ import absolute_import

import os
import shutil
import tempfile

import httpretty

from invenio_github.badge import create_badge, shieldsio_encode

SVG = (
    """<svg xmlns="http://www.w3.org/2000/svg" width="135" """
    """height="20"><linearGradient id="b" x2="0" y2="100%">"""
    """<stop offset="0" stop-color="#bbb" stop-opacity=".1"/>"""
    """<stop offset="1" stop-opacity=".1"/></linearGradient>"""
    """<mask id="a">"""
    """<rect width="135" height="20" rx="3" fill="#fff"/></mask>"""
    """<g mask="url(#a)"><path fill="#555" d="M0 0h33v20H0z"/>"""
    """<path fill="#007ec6" d="M33 0h102v20H33z"/>"""
    """<path fill="url(#b)" d="M0 0h135v20H0z"/></g>"""
    """<g fill="#fff" text-anchor="middle" """
    """font-family="DejaVu Sans,Verdana,Geneva,sans-serif" """
    """font-size="11"><text x="17.5" y="15" fill="#010101" """
    """fill-opacity=".3">DOI</text><text x="17.5" y="14">DOI</text>"""
    """<text x="83" y="15" fill="#010101" fill-opacity=".3">"""
    """10.1234/foo.bar</text><text x="83" y="14">10.1234/foo.bar"""
    """</text></g></svg>"""
)


def test_shieldsio_encode(app):
    """Test encoding of text for shields.io."""
    assert shieldsio_encode("10.1234/foo-bar_") == "10.1234%2Ffoo--bar__"


def test_create_badge(app):
    """Test create_badge method."""
    badge_url = "%sDOI-10.1234%%2Ffoo.bar-blue.svg?style=flat" % \
        app.config["GITHUB_SHIELDSIO_BASE_URL"]

    httpretty.enable()
    httpretty.register_uri(
        httpretty.GET,
        badge_url,
        body=SVG,
        content_type="image/svg+xml",
    )

    output = os.path.join(app.instance_path, "test.svg")

    create_badge(
        "DOI",
        "10.1234/foo.bar",
        "blue",
        output,
        style="flat",
    )

    assert os.path.exists(output)
    httpretty.disable()
