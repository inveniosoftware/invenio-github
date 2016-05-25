# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016 CERN.
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


"""GitHub bundles for user interface."""

from invenio.base.bundles import invenio as _i
from invenio.base.bundles import jquery as _j
from invenio_assets import Bundle, RequireJSFilter

#
# Site-wide JS
#
js = Bundle(
    "js/github/init.js",
    output="github.js",
    filters=RequireJSFilter(exclude=[_j, _i]),
    weight=60,
    bower={
        "bootstrap-switch": "3.0.2",
    }
)

styles = Bundle(
    "vendors/bootstrap-switch/src/less/bootstrap3/build.less",
    output="github.css",
    filters="less,cleancss",
    weight=60,
    bower={
        "bootstrap-switch": "3.0.2",
    }
)
