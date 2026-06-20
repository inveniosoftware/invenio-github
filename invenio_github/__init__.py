# SPDX-FileCopyrightText: 2023-2025 CERN.
# SPDX-FileCopyrightText: 2024-2026 Graz University of Technology.
# SPDX-License-Identifier: MIT

"""Invenio module that adds GitHub integration to the platform."""

from .ext import InvenioGitHub

__version__ = "7.0.0"

__all__ = ("__version__", "InvenioGitHub")
