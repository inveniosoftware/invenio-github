# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016-2019 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Admin model views for GitHub."""

from __future__ import absolute_import, print_function

from flask_admin.contrib.sqla import ModelView

from .models import Release, Repository


def _(x):
    """Identity function for string extraction."""
    return x


class RepositoryModelView(ModelView):
    """ModelView for the GitHub Repository."""

    can_create = True
    can_edit = True
    can_delete = False
    can_view_details = True
    column_display_all_relations = True
    column_list = (
        'id',
        'github_id',
        'name',
        'user',
        'enabled',
        'ping',
        'hook',
    )
    column_searchable_list = ('github_id', 'name', 'user.email')


class ReleaseModelView(ModelView):
    """ModelView for the GitHub Release."""

    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True
    column_display_all_relations = True
    column_list = (
        'repository',
        'tag',
        'status',
        'id',
        'release_id',
        'record_id',
        'record',
    )
    column_searchable_list = (
        'tag',
        'status',
        'repository.name',
        'repository.github_id',
    )


repository_adminview = dict(
    model=Repository,
    modelview=RepositoryModelView,
    category=_('GitHub'),
)

release_adminview = dict(
    model=Release,
    modelview=ReleaseModelView,
    category=_('GitHub'),
)
