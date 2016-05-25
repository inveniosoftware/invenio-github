# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016 CERN.
#
# Invenio is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Models for GitHub integration."""

from __future__ import absolute_import

import re
import uuid

from celery import shared_task
from flask import current_app, request, url_for
from invenio_accounts.models import User
from invenio_db import db
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import validates
from sqlalchemy_utils.models import Timestamp
from sqlalchemy_utils.types import JSONType, UUIDType


class Repository(db.Model, Timestamp):
    """Information about a GitHub repository."""

    __tablename__ = 'github_repositories'

    id = db.Column(
        UUIDType,
        primary_key=True,
        default=uuid.uuid4,
    )
    """Event identifier."""

    # TODO shall we use Text instead?
    name = db.Column(db.String(255), index=True, nullable=False)
    """Fully qualified name of the repository including user/organization."""

    user_id = db.Column(
        db.Integer,
        db.ForeignKey(User.id),
        nullable=True,
    )
    """User identifier."""

    @classmethod
    def enable(cls, name):
        """Enable hook for repository."""
        raise NotImplemented()

    @classmethod
    def disable(cls, name):
        """Disable hook for repository."""
        raise NotImplemented()
