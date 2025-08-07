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
        "vcs_repositories", sa.Column("provider", sa.String(255), nullable=False)
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
    )
    op.drop_column("github_repositories", "provider")

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
    # ### end Alembic commands ###
