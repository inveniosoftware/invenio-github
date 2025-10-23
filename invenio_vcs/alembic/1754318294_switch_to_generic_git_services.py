# -*- coding: utf-8 -*-
# This file is part of Invenio.
# Copyright (C) 2025 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Switch to a generic VCS module (not GitHub-specific)."""


import sqlalchemy as sa
from alembic import op
from sqlalchemy_utils import JSONType, UUIDType

# revision identifiers, used by Alembic.
revision = "1754318294"
down_revision = "b0eaee37b545"
# You cannot rename an Alembic branch. So we will have to keep
# the branch label `invenio-github` despite changing the module
# to `invenio-vcs`.
branch_labels = ()
depends_on = None


def upgrade():
    """Upgrade database."""
    op.create_table(
        "vcs_repositories",
        sa.Column("id", UUIDType()),
        sa.Column("provider_id", sa.String(length=255), nullable=False),
        sa.Column(
            "provider", sa.String(length=255), nullable=False, server_default="github"
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "default_branch",
            sa.String(length=255),
            nullable=False,
            server_default="main",
        ),
        sa.Column("description", sa.String(length=10000)),
        sa.Column("license_spdx", sa.String(length=255)),
        sa.Column("hook", sa.String(length=255)),
        sa.Column("enabled_by_user_id", sa.Integer),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("updated", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vcs_repositories")),
        sa.ForeignKeyConstraint(
            ["enabled_by_user_id"],
            ["accounts_user.id"],
            name=op.f("fk_vcs_repository_enabled_by_user_id_accounts_user"),
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_id",
            name=op.f("uq_vcs_repositories_provider_provider_id"),
        ),
        sa.UniqueConstraint(
            "provider",
            "name",
            name=op.f("uq_vcs_repositories_provider_name"),
        ),
    )

    op.create_table(
        "vcs_repository_users",
        sa.Column("repository_id", UUIDType()),
        sa.Column("user_id", sa.Integer()),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("updated", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint(
            "repository_id", "user_id", name=op.f("pk_vcs_repository_users")
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["vcs_repositories.id"],
            name=op.f("fk_vcs_repository_users_repository_id_vcs_repositories"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["accounts_user.id"],
            name=op.f("fk_vcs_repository_users_user_id_accounts_user"),
        ),
    )

    op.create_table(
        "vcs_releases",
        sa.Column("id", UUIDType()),
        sa.Column("provider_id", sa.String(length=255), nullable=False),
        sa.Column(
            "provider", sa.String(length=255), nullable=False, server_default="github"
        ),
        sa.Column("tag", sa.String(length=255), nullable=False),
        sa.Column(
            "errors",
            sa.JSON()
            .with_variant(sa.dialects.postgresql.JSONB(), "postgresql")
            .with_variant(JSONType(), "sqlite")
            .with_variant(JSONType(), "mysql"),
        ),
        sa.Column("repository_id", UUIDType(), nullable=False),
        sa.Column("event_id", UUIDType(), nullable=True),
        sa.Column("record_id", UUIDType()),
        sa.Column("status", sa.CHAR(1)),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("updated", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vcs_releases")),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["webhooks_events.id"],
            name=op.f("fk_vcs_releases_event_id_webhooks_events"),
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["vcs_repositories.id"],
            name=op.f("fk_vcs_releases_repository_id_vcs_repositories"),
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_id",
            name=op.f("uq_vcs_releases_provider_id_provider"),
        ),
    )

    op.create_index(
        op.f("ix_vcs_releases_record_id"),
        table_name="vcs_releases",
        columns=["record_id"],
    )


def downgrade():
    """Downgrade database."""
    op.drop_table("vcs_releases")
    op.drop_table("vcs_repository_users")
    op.drop_table("vcs_repositories")
