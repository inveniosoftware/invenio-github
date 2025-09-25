# -*- coding: utf-8 -*-
#
# Copyright (C) 2023 CERN.
#
# Invenio-Github is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
"""JS/CSS Webpack bundles for theme."""

from invenio_assets.webpack import WebpackThemeBundle

theme = WebpackThemeBundle(
    __name__,
    "assets",
    default="semantic-ui",
    themes={
        "semantic-ui": dict(
            entry={
                # Add your webpack entrypoints
                "invenio-vcs-init": "./js/invenio_vcs/index.js",
            },
            dependencies={"@babel/runtime": "^7.9.0"},
        ),
    },
)
