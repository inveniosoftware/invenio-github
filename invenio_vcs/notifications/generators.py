# -*- coding: utf-8 -*-
# This file is part of Invenio.
# Copyright (C) 2025 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Class implementations required for invenio-notifications."""

from invenio_access.permissions import system_identity
from invenio_notifications.models import Recipient
from invenio_notifications.services.generators import RecipientGenerator
from invenio_records.dictutils import dict_lookup
from invenio_search.engine import dsl
from invenio_users_resources.proxies import current_users_service

from invenio_vcs.models import Repository


class RepositoryUsersRecipient(RecipientGenerator):
    """Recipient generator for all users with access to a given repository."""

    def __init__(self, provider_key: str, provider_id_key: str) -> None:
        """Constructor."""
        super().__init__()
        self.provider_key = provider_key
        self.provider_id_key = provider_id_key

    def __call__(self, notification, recipients: dict):
        """Look up the IDs of users with access to the repo and add their profile data to the `recipients` dict."""
        provider = dict_lookup(notification.context, self.provider_key)
        provider_id = dict_lookup(notification.context, self.provider_id_key)

        repository = Repository.get(provider, provider_id)
        assert repository is not None
        user_associations = repository.list_users()

        user_ids: set[str] = set()
        for association in user_associations.mappings():
            user_id = association["user_id"]
            user_ids.add(user_id)

        if not user_ids:
            return recipients

        filter = dsl.Q("terms", **{"id": list(user_ids)})
        users = current_users_service.scan(system_identity, extra_filter=filter)
        for u in users:
            recipients[u["id"]] = Recipient(data=u)
        return recipients
