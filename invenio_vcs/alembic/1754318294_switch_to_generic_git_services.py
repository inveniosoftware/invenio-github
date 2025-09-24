#
# This file is part of Invenio.
# Copyright (C) 2025 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Switch to generic git services"""

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.ext.mutable import MutableDict
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
        # We use the provider name "github" by default as this is what we're already using across the codebase
        sa.Column("provider", sa.String(255), nullable=False, server_default="github"),
    )
    op.add_column(
        "vcs_repositories",
        sa.Column(
            "default_branch", sa.String(255), nullable=False, server_default="master"
        ),
    )
    op.add_column(
        "vcs_repositories", sa.Column("description", sa.String(10000), nullable=True)
    )
    op.add_column(
        # Nullable for now (see below)
        "vcs_repositories",
        sa.Column("html_url", sa.String(10000), nullable=True),
    )
    op.add_column(
        "vcs_repositories", sa.Column("license_spdx", sa.String(255), nullable=True)
    )
    op.alter_column("vcs_repositories", "user_id", new_column_name="enabled_by_id")
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

    # Migrate data from the OAuth remote `extra_data` field to the repositories table
    # where we will now store everything directly.
    #
    # We need to recreate the SQLAlchemy models for `RemoteAccount` and `Repository` here but
    # in a much more lightweight way. We cannot simply import the models because (a) they depend
    # on the full Invenio app being initialised and all extensions available and (b) we need
    # to work with the models as they stand precisely at this point in the migration chain
    # rather than the model file itself which may be at a later commit.
    #
    # We only include here the columns, constraints, and relations that we actually need to
    # perform the migration, therefore keeping these models as lightweight as possible.
    remote_account_table = sa.table(
        "oauthclient_remoteaccount",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("account_user.id")),
        sa.Column("client_id", sa.String(255)),
        sa.Column("extra_data", MutableDict.as_mutable(JSONType)),
    )
    vcs_repositories_table = sa.table(
        "vcs_repositories",
        sa.Column("id", UUIDType, primary_key=True),
        sa.Column("provider_id", sa.String(255), nullable=True),
        sa.Column("provider", sa.String(255), nullable=True),
        sa.Column("description", sa.String(10000), nullable=True),
        sa.Column("html_url", sa.String(10000), nullable=False),
        sa.Column("license_spdx", sa.String(255), nullable=True),
        sa.Column("default_branch", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hook", sa.String(255), nullable=True),
        sa.Column(
            "enabled_by_id", sa.Integer, sa.ForeignKey("account_user.id"), nullable=True
        ),
        sa.Column("created", sa.DateTime, nullable=False),
        sa.Column("updated", sa.DateTime, nullable=False),
    )

    # This is the recommended way to run SQLAlchemy operations in a migration, see https://alembic.sqlalchemy.org/en/latest/ops.html#alembic.operations.Operations.execute
    session = op.get_bind()

    # We don't know the client ID as this is a config variable.
    # So to find the RemoteAccounts that correspond to GitHub, we need to check for the existence
    # of the `repos` key in the `extra_data` JSON. We cannot make this very efficient sadly, because
    # (a) in Postgres we are using JSON not JSONB so there is no efficient JSON querying and (b) the
    # instance might be using MySQL/SQLite where we store it as `TEXT`.

    remote_accounts = session.execute(sa.select(remote_account_table))
    for remote_account in remote_accounts.mappings():
        if "repos" not in remote_account["extra_data"]:
            continue

        repos = remote_account["extra_data"]["repos"]

        for id, github_repo in repos.items():
            # `id` (the dict key) is a string because JSON keys must be strings

            matching_db_repo_id = session.scalar(
                sa.select(vcs_repositories_table).filter_by(provider_id=id)
            )

            if matching_db_repo_id is None:
                # We are now storing _all_ repositories (even non-enabled ones) in the DB.
                # The repo-user association will be created on the first sync after this migration, we need to download
                # the list of users with access to the repo from the GitHub API.
                session.execute(
                    vcs_repositories_table.insert().values(
                        id=uuid.uuid4(),
                        provider_id=id,
                        provider="github",
                        description=github_repo["description"],
                        name=github_repo["full_name"],
                        default_branch=github_repo["default_branch"],
                        # So far we have only supported github.com so we can safely assume the URL
                        html_url=f'https://github.com/{github_repo["full_name"]}',
                        # We have never stored this, it is queried at runtime right now. When the first
                        # sync happens after this migration, we will download all the license IDs from the VCS.
                        license_spdx=None,
                        # This repo wasn't enabled
                        hook=None,
                        enabled_by_id=None,
                        created=datetime.now(tz=timezone.utc),
                        updated=datetime.now(tz=timezone.utc),
                    )
                )
            else:
                session.execute(
                    vcs_repositories_table.update()
                    .filter_by(id=matching_db_repo_id)
                    .values(
                        description=github_repo["description"],
                        name=github_repo["full_name"],
                        default_branch=github_repo["default_branch"],
                        html_url=f'https://github.com/{github_repo["full_name"]}',
                        updated=datetime.now(tz=timezone.utc),
                    )
                )

        # Remove `repos` from the existing `extra_data`, leaving only the last sync timestamp
        session.execute(
            remote_account_table.update()
            .filter_by(id=remote_account["id"])
            .values(extra_data={"last_sync": remote_account["extra_data"]["last_sync"]})
        )

    # We initially set this to nullable=True so we can create the column without an error
    # (it would be null for existing records) but after the SQLAlchemy operations above we
    # have populated it so we can mark it non-nullable.
    op.alter_column(
        "vcs_repositories", "html_url", nullable=False, existing_nullable=True
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
    op.add_column(
        "vcs_releases",
        sa.Column("provider", sa.String(255), nullable=False, server_default="github"),
    )
    if op.get_context().dialect.name == "postgresql":
        op.alter_column(
            "vcs_releases",
            "errors",
            type_=sa.dialects.postgresql.JSONB,
            postgresql_using="errors::text::jsonb",
        )

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

    op.create_table(
        "vcs_repository_users",
        sa.Column("repository_id", UUIDType(), primary_key=True),
        sa.Column("user_id", sa.Integer(), primary_key=True),
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
    # ### end Alembic commands ###


def downgrade():
    """Downgrade database."""

    # Currently, the downgrade can only be peformed **without data**. The tables are transformed but
    # data will not be successfully migrated. The upgrade migration has a large amount of custom logic
    # for migrating the data into the new format, and this is not replicated/reversed for downgrading.

    op.alter_column(
        "vcs_repositories",
        "enabled_by_id",
        new_column_name="user_id",
    )
    op.drop_table("vcs_repository_users")

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
    if op.get_context().dialect.name == "postgresql":
        op.alter_column(
            "github_releases",
            "errors",
            type_=sa.dialects.postgresql.JSON,
            postgresql_using="errors::text::json",
        )
    op.create_unique_constraint(
        op.f("uq_github_releases_release_id"),
        table_name="github_releases",
        columns=["release_id"],
    )
    # ### end Alembic commands ###
