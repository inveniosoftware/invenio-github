# -*- coding: utf-8 -*-
#
# Copyright (C) 2025 CERN.
#
# Invenio-VCS is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.
"""Migration script for v3 (old GitHub-only integration) to v4 (new generic VCS integration)."""

import sys
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic.runtime.migration import MigrationContext
from click import progressbar, secho
from invenio_db import db
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy_utils import JSONType, UUIDType

# Lightweight models for all of the tables (incl old and new versions)
remote_account_table = sa.table(
    "oauthclient_remoteaccount",
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("account_user.id")),
    sa.Column("client_id", sa.String(255)),
    # We may have changed this if we merge https://github.com/inveniosoftware/invenio-oauthclient/pull/360
    # but we're only reading this column so it shouldn't make a difference.
    sa.Column("extra_data", MutableDict.as_mutable(JSONType)),
)
github_repositories_table = sa.table(
    "github_repositories",
    sa.Column("id", UUIDType, primary_key=True),
    sa.Column("github_id", sa.String(255), nullable=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("hook", sa.Integer, nullable=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("account_user.id"), nullable=True),
    sa.Column("created", sa.DateTime, nullable=False),
    sa.Column("updated", sa.DateTime, nullable=False),
)
vcs_repositories_table = sa.table(
    "vcs_repositories",
    sa.Column("id", UUIDType, primary_key=True),
    sa.Column("provider_id", sa.String(255), nullable=False),
    sa.Column("provider", sa.String(255), nullable=False),
    sa.Column("description", sa.String(10000), nullable=True),
    sa.Column("license_spdx", sa.String(255), nullable=True),
    sa.Column("default_branch", sa.String(255), nullable=False),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("hook", sa.String(255), nullable=True),
    sa.Column(
        "enabled_by_user_id",
        sa.Integer,
        sa.ForeignKey("account_user.id"),
        nullable=True,
    ),
    sa.Column("created", sa.DateTime, nullable=False),
    sa.Column("updated", sa.DateTime, nullable=False),
)
github_releases_table = sa.table(
    "github_releases",
    sa.Column("id", UUIDType, primary_key=True),
    sa.Column("release_id", sa.Integer, primary_key=True),
    sa.Column("tag", sa.String(255), nullable=True),
    sa.Column("errors", MutableDict.as_mutable(JSONType), nullable=True),
    sa.Column(
        "repository_id",
        UUIDType,
        sa.ForeignKey("github_repositories.id"),
        nullable=True,
    ),
    sa.Column("event_id", UUIDType, sa.ForeignKey("webhooks_events.id"), nullable=True),
    sa.Column("record_id", UUIDType, nullable=True),
    sa.Column("status", sa.CHAR(1), nullable=False),
    sa.Column("created", sa.DateTime, nullable=False),
    sa.Column("updated", sa.DateTime, nullable=False),
)
vcs_releases_table = sa.table(
    "vcs_releases",
    sa.Column("id", UUIDType, primary_key=True),
    sa.Column("provider_id", sa.String(255), nullable=False),
    sa.Column("provider", sa.String(255), nullable=False),
    sa.Column("tag", sa.String(255), nullable=False),
    sa.Column(
        "errors",
        MutableDict.as_mutable(
            sa.JSON()
            .with_variant(postgresql.JSONB(), "postgresql")
            .with_variant(JSONType(), "sqlite")
            .with_variant(JSONType(), "mysql")
        ),
        nullable=True,
    ),
    sa.Column(
        "repository_id",
        UUIDType,
        sa.ForeignKey("vcs_repositories.id"),
        nullable=True,
    ),
    sa.Column(
        "event_id", UUIDType, sa.ForeignKey("webhooks_events.id"), nullable=False
    ),
    sa.Column("record_id", UUIDType, nullable=True),
    sa.Column("status", sa.CHAR(1), nullable=False),
    sa.Column("created", sa.DateTime, nullable=False),
    sa.Column("updated", sa.DateTime, nullable=False),
)


def run_upgrade_for_oauthclient_repositories():
    """Move the JSON repos from oauthclient_remoteaccount to the new vcs_repositories table."""

    secho(
        "Migrating JSON data from oauthclient_remoteaccount into vcs_repositories table...",
        fg="green",
    )

    # We don't know the client ID as this is a config variable.
    # So to find the RemoteAccounts that correspond to GitHub, we need to check for the existence
    # of the `repos` key in the `extra_data` JSON. We cannot make this very efficient sadly, because
    # (a) in Postgres we are using JSON not JSONB so there is no efficient JSON querying and (b) the
    # instance might be using MySQL/SQLite where we store it as `TEXT`.

    # We can make this a little bit faster if https://github.com/inveniosoftware/invenio-oauthclient/pull/328
    # were merged and released and all instances were using it, but this is unlikely to be the case
    # by the time we release Invenio VCS v4.

    remote_accounts = db.session.execute(sa.select(remote_account_table)).mappings()
    with progressbar(remote_accounts) as remote_accounts:
        for remote_account in remote_accounts:
            if "repos" not in remote_account["extra_data"]:
                continue

            repos = remote_account["extra_data"]["repos"]

            for id, github_repo in repos.items():
                # `id` (the dict key) is a string because JSON keys must be strings

                # We might have already created it for another user
                matching_db_repo_id = db.session.scalar(
                    sa.select(vcs_repositories_table).filter_by(provider_id=id)
                )

                if matching_db_repo_id is None:
                    # We are now storing _all_ repositories (even non-enabled ones) in the DB.
                    # The repo-user association will be created on the first sync after this migration, we need to download
                    # the list of users with access to the repo from the GitHub API.
                    db.session.execute(
                        vcs_repositories_table.insert().values(
                            id=uuid.uuid4(),
                            provider_id=id,
                            provider="github",
                            description=github_repo["description"],
                            name=github_repo["full_name"],
                            default_branch=github_repo["default_branch"],
                            # We have never stored this, it is queried at runtime right now. When the first
                            # sync happens after this migration, we will download all the license IDs from the VCS.
                            license_spdx=None,
                            # This repo wasn't enabled, since it is not already in the repositories table.
                            hook=None,
                            enabled_by_user_id=None,
                            created=datetime.now(tz=timezone.utc),
                            updated=datetime.now(tz=timezone.utc),
                        )
                    )
                else:
                    db.session.execute(
                        vcs_repositories_table.update()
                        .filter_by(id=matching_db_repo_id)
                        .values(
                            description=github_repo["description"],
                            name=github_repo["full_name"],
                            default_branch=github_repo["default_branch"],
                            updated=datetime.now(tz=timezone.utc),
                        )
                    )

            # Remove `repos` from the existing `extra_data`, leaving only the last sync timestamp
            db.session.execute(
                remote_account_table.update()
                .filter_by(id=remote_account["id"])
                .values(
                    extra_data={"last_sync": remote_account["extra_data"]["last_sync"]}
                )
            )

    db.session.commit()


def run_upgrade_for_existing_db_repositories():
    """Move over any old rows from github_repositories that weren't attached to any user (for whatever reason).

    These are (almost) all repos that are enabled and have a hook. However repos that have been enabled and then
    later disabled are also included.
    """

    secho(
        "Migrating old repo table entries to new vcs_repositories table...", fg="green"
    )

    old_db_repos = db.session.execute(sa.select(github_repositories_table)).mappings()
    with progressbar(old_db_repos) as old_db_repos:
        for old_db_repo in old_db_repos:
            matching_new_repo_id = db.session.scalar(
                sa.select(
                    vcs_repositories_table.c.id,
                ).filter_by(provider_id=str(old_db_repo["github_id"]))
            )

            if matching_new_repo_id is None:
                # We only have very limited metadata available at this point.
                # The first sync job after this migration will fill in the rest.
                db.session.execute(
                    vcs_repositories_table.insert().values(
                        id=old_db_repo["id"],
                        provider_id=str(old_db_repo["github_id"]),
                        provider="github",
                        name=old_db_repo["name"],
                        default_branch="main",
                        license_spdx=None,
                        hook=old_db_repo["hook"],
                        enabled_by_user_id=old_db_repo["user_id"],
                        created=old_db_repo["created"],
                        updated=datetime.now(tz=timezone.utc),
                    )
                )
            else:
                db.session.execute(
                    vcs_repositories_table.update()
                    .filter_by(id=matching_new_repo_id)
                    .values(
                        id=old_db_repo["id"],
                        hook=str(old_db_repo["hook"]),
                        enabled_by_user_id=old_db_repo["user_id"],
                        created=old_db_repo["created"],
                    )
                )

    db.session.commit()


def run_upgrade_for_releases():
    """Copy releases from old table to new vcs_releases table."""

    secho(
        "Migrating old release table entries to new vcs_releases table...", fg="green"
    )

    # Finally, we copy over the releases
    old_db_releases = db.session.execute(sa.select(github_releases_table)).mappings()
    with progressbar(old_db_releases) as old_db_releases:
        for old_db_release in old_db_releases:
            # Since we've created all the repos, we know due to referential integrity that this release's repo ID corresponds
            # to a valid and existent repo.

            db.session.execute(
                vcs_releases_table.insert().values(
                    id=old_db_release["id"],
                    provider_id=str(old_db_release["release_id"]),
                    provider="github",
                    tag=old_db_release["tag"],
                    errors=old_db_release["errors"],
                    repository_id=old_db_release["repository_id"],
                    event_id=old_db_release["event_id"],
                    record_id=old_db_release["record_id"],
                    status=old_db_release["status"],
                    created=old_db_release["created"],
                    updated=datetime.now(tz=timezone.utc),
                )
            )

    db.session.commit()


def verify_alembic_version(expected_revision: str):
    """Verify that the Alembic migration for this version has been executed.

    Attempting to run the other steps of this upgrade script on an old migration version
    will have unexpected consequences.
    """

    secho("Verifying Alembic migration is up-to-date...", fg="green")

    with db.engine.connect() as connection:
        alembic_ctx = MigrationContext.configure(connection)
        # This returns a tuple of the versions of each branch (without the branch name).
        current_revs = alembic_ctx.get_current_heads()

        # We just need to check that our expected version ID is included in the tuple
        if expected_revision not in current_revs:
            secho(
                "The invenio-github Alembic branch is not at the latest revision. Please upgrade it before continuing.",
                fg="red",
            )
            sys.exit(1)


def execute_upgrade():
    """Execute all of the steps for the upgrade of InvenioVCS v3 to v4."""
    secho("Starting Invenio-VCS v3->v4 data migration...", fg="green")

    verify_alembic_version("1754318294")

    run_upgrade_for_oauthclient_repositories()
    run_upgrade_for_existing_db_repositories()
    run_upgrade_for_releases()


if __name__ == "__main__":
    execute_upgrade()
