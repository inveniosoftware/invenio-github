# -*- coding: utf-8 -*-
# This file is part of Invenio.
# Copyright (C) 2025 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""Abstract provider-specific patcher class."""

from abc import ABC, abstractmethod
from typing import Any, Iterator

from invenio_vcs.generic_models import (
    GenericContributor,
    GenericOwner,
    GenericRelease,
    GenericRepository,
    GenericUser,
    GenericWebhook,
)
from invenio_vcs.providers import (
    RepositoryServiceProvider,
    RepositoryServiceProviderFactory,
)


class TestProviderPatcher(ABC):
    """Interface for specifying a provider-specific primitive API patch and other test helpers."""

    def __init__(self, test_user) -> None:
        """Constructor."""
        self.provider = self.provider_factory().for_user(test_user.id)

    @staticmethod
    @abstractmethod
    def provider_factory() -> RepositoryServiceProviderFactory:
        """Return the factory for the provider."""
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def test_webhook_payload(
        generic_repository: GenericRepository,
        generic_release: GenericRelease,
        generic_repo_owner: GenericOwner,
    ) -> dict[str, Any]:
        """Return an example webhook payload."""
        raise NotImplementedError

    @abstractmethod
    def patch(
        self,
        test_generic_repositories: list[GenericRepository],
        test_generic_contributors: list[GenericContributor],
        test_collaborators: list[dict[str, Any]],
        test_generic_webhooks: list[GenericWebhook],
        test_generic_user: GenericUser,
        test_file: dict[str, Any],
    ) -> Iterator[RepositoryServiceProvider]:
        """Implement the patch.

        This should be applied to the primitives of the provider's API and not to e.g. the provider methods
        themselves, as that would eliminate the purpose of testing the provider functionality.

        At the end, this should yield within the patch context to ensure the patch is applied throughout the
        test case run and then unapplied at the end for consistency.
        """
        raise NotImplementedError
