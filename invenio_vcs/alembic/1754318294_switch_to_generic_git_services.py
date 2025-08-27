#
# This file is part of Invenio.
# Copyright (C) 2016-2018 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Switch to generic git services"""

import sqlalchemy as sa
from alembic import op

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
    op.rename_table("github_repositories", "vcs_repositories")
    op.alter_column(
        "vcs_repositories",
        "github_id",
        new_column_name="provider_id",
        type_=sa.String(length=255),
        nullable=False,
        existing_type=sa.Integer(),
        existing_nullable=True,
    )
    op.alter_column(
        "vcs_repositories",
        "hook",
        type_=sa.String(length=255),
        nullable=True,
        existing_type=sa.Integer(),
        existing_nullable=True,
    )
    op.add_column(
        "vcs_repositories",
        sa.Column("provider", sa.String(255), nullable=False),
    )
    op.add_column(
        "vcs_repositories",
        sa.Column("default_branch", sa.String(255), nullable=False, default="master"),
    )
    op.add_column(
        "vcs_repositories", sa.Column("description", sa.String(10000), nullable=True)
    )
    op.add_column(
        "vcs_repositories", sa.Column("html_url", sa.String(10000), nullable=False)
    )
    op.add_column(
        "vcs_repositories", sa.Column("license_spdx", sa.String(255), nullable=True)
    )
    op.drop_index("ix_github_repositories_name")
    op.drop_index("ix_github_repositories_github_id")

    # Because they rely on the `provider` column, these are automatically
    # deleted when downgrading so we don't need a separate drop command
    # for them.
    op.create_unique_constraint(
        constraint_name=op.f("uq_vcs_repositories_provider_provider_id"),
        table_name="vcs_repositories",
        columns=["provider", "provider_id"],
    )
    op.create_unique_constraint(
        constraint_name=op.f("uq_vcs_repositories_provider_name"),
        table_name="vcs_repositories",
        columns=["provider", "name"],
    )

    op.rename_table("github_releases", "vcs_releases")
    op.alter_column(
        "vcs_releases",
        "release_id",
        new_column_name="provider_id",
        type_=sa.String(length=255),
        nullable=False,
        existing_type=sa.Integer(),
        existing_nullable=True,
    )
    op.add_column("vcs_releases", sa.Column("provider", sa.String(255), nullable=False))

    op.drop_constraint(
        op.f("uq_github_releases_release_id"), table_name="vcs_releases", type_="unique"
    )
    # A given provider cannot have duplicate repository IDs.
    # These constraints are also inherently deleted when the `provider` column is dropped
    op.create_unique_constraint(
        constraint_name=op.f("uq_vcs_releases_provider_id_provider"),
        table_name="vcs_releases",
        columns=["provider_id", "provider"],
    )
    # A specific repository from a given provider cannot have multiple releases of the same tag
    op.create_unique_constraint(
        constraint_name=op.f("uq_vcs_releases_provider_id_provider_tag"),
        table_name="vcs_releases",
        columns=["provider_id", "provider", "tag"],
    )
    # ### end Alembic commands ###


def downgrade():
    """Downgrade database."""
    op.rename_table("vcs_repositories", "github_repositories")
    op.alter_column(
        "github_repositories",
        "provider_id",
        new_column_name="github_id",
        type_=sa.Integer(),
        nullable=True,
        existing_type=sa.String(length=255),
        existing_nullable=False,
        postgresql_using="provider_id::integer",
    )
    op.alter_column(
        "github_repositories",
        "hook",
        type_=sa.Integer(),
        nullable=True,
        existing_type=sa.String(length=255),
        existing_nullable=True,
        postgresql_using="hook::integer",
    )
    op.drop_column("github_repositories", "provider")
    op.drop_column("github_repositories", "description")
    op.drop_column("github_repositories", "html_url")
    op.drop_column("github_repositories", "license_spdx")
    op.drop_column("github_repositories", "default_branch")
    op.create_index(
        op.f("ix_github_repositories_github_id"),
        "github_repositories",
        ["github_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_github_repositories_name"),
        "github_repositories",
        ["name"],
        unique=True,
    )

    op.rename_table("vcs_releases", "github_releases")
    op.alter_column(
        "github_releases",
        "provider_id",
        new_column_name="release_id",
        type_=sa.Integer(),
        nullable=True,
        existing_type=sa.String(length=255),
        existing_nullable=False,
        postgresql_using="provider_id::integer",
    )
    op.drop_column("github_releases", "provider")
    op.create_unique_constraint(
        op.f("uq_github_releases_release_id"),
        table_name="github_releases",
        columns=["release_id"],
    )
    # ### end Alembic commands ###
