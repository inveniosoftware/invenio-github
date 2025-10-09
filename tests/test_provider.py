# -*- coding: utf-8 -*-
#
# Copyright (C) 2025 CERN.
#
# Invenio-VCS is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
"""Test invenio-vcs provider layer."""

from invenio_vcs.generic_models import (
    GenericContributor,
    GenericRepository,
    GenericWebhook,
)
from invenio_vcs.providers import RepositoryServiceProvider
from invenio_vcs.service import VCSService


def test_vcs_provider_list_repositories(
    vcs_provider: RepositoryServiceProvider,
    test_generic_repositories: list[GenericRepository],
):
    repos = vcs_provider.list_repositories()
    assert repos is not None
    assert len(repos) == len(test_generic_repositories)
    assert isinstance(repos[test_generic_repositories[0].id], GenericRepository)


def test_vcs_provider_list_hooks(
    vcs_provider: RepositoryServiceProvider,
    test_generic_repositories: list[GenericRepository],
    test_generic_webhooks: list[GenericWebhook],
):
    repo_id = test_generic_repositories[0].id
    test_hooks = list(
        filter(lambda h: h.repository_id == repo_id, test_generic_webhooks)
    )
    hooks = vcs_provider.list_repository_webhooks(repo_id)
    assert hooks is not None
    assert len(hooks) == len(test_hooks)
    assert hooks[0].id == test_hooks[0].id


def test_vcs_provider_list_user_ids(vcs_provider: RepositoryServiceProvider):
    # This should correspond to the IDs in `test_collaborators` at least roughly
    user_ids = vcs_provider.list_repository_user_ids("1")
    assert user_ids is not None
    # Only one user should have admin privileges
    assert len(user_ids) == 1
    assert user_ids[0] == "1"


def test_vcs_provider_get_repository(vcs_provider: RepositoryServiceProvider):
    repo = vcs_provider.get_repository("1")
    assert repo is not None


def test_vcs_provider_create_hook(
    # For this test, we need to init accounts so we need to use the service
    vcs_service: VCSService,
):
    repo_id = "1"
    hook_created = vcs_service.provider.create_webhook(repository_id=repo_id)
    assert hook_created is not None


def test_vcs_provider_get_own_user(vcs_provider: RepositoryServiceProvider):
    own_user = vcs_provider.get_own_user()
    assert own_user is not None
    assert own_user.id == "1"


def test_vcs_provider_list_repository_contributors(
    vcs_provider: RepositoryServiceProvider,
    test_generic_contributors: list[GenericContributor],
    test_generic_repositories: list[GenericRepository],
):
    contributors = vcs_provider.list_repository_contributors(
        test_generic_repositories[0].id, 10
    )
    assert contributors is not None
    assert len(contributors) == len(test_generic_contributors)
    # The list order is arbitrary so we cannot validate that the IDs match up


def test_vcs_provider_get_repository_owner(
    vcs_provider: RepositoryServiceProvider,
    test_generic_repositories: list[GenericRepository],
):
    owner = vcs_provider.get_repository_owner(test_generic_repositories[0].id)
    assert owner is not None
    # We don't store the owner id in the generic repository model
    assert owner.id == "1"
