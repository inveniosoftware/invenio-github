..
    This file is part of Invenio.
    Copyright (C) 2025 CERN.

    Invenio is free software; you can redistribute it and/or modify it
    under the terms of the MIT License; see LICENSE file for more details.

Upgrading
=========

======
v4.0.0
======

This version consists of a major refactor of the module and a full rename to ``invenio-vcs`` (from ``invenio-github``).
The new version has now been made generic and can support any VCS provider by implementing the relevant abstract classes.

Contrib implementations are provided for GitHub and GitLab.
GitHub is supported with the exact same set of features as before, meaning this module can continue to be used for the original
purpose of ``invenio-github`` with just some migrations and configuration changes required.

Please follow this guide if:

- you are **not** using InvenioRDM; or
- you would like to try out ``invenio-vcs`` before InvenioRDM v14 is released.

  - This is not officially supported but should work for the most part.

RDM-specific instructions can instead be found in the `InvenioRDM upgrade guide <https://inveniordm.docs.cern.ch/releases/vNext/upgrade-vNext/>`_.

--------------------------
1. Update the dependencies
--------------------------

In your ``Pipfile`` (or any similar file you are using to manage dependencies), change the name and version of the ``invenio-vcs`` packages.
Additionally, you will need to ensure some other dependencies are up to date for compatibility with the new changes.

.. code-block:: toml

   [packages]
   # ...
   invenio-vcs = ">=4.0.0,<5.0.0"
   invenio-rdm-records = "TODO"
   invenio-app-rdm = "TODO"
   invenio-oauthclient = "TODO"

.. note::

   ``invenio-vcs`` is no longer packaged by default with InvenioRDM, as was the case with ``invenio-github``.
   You must declare it as an explicit dependency on the instance level.

Next, run the install operation and make sure the old module is no longer installed.
Having both installed simultaneously will lead to numerous conflicts, especially with Alembic migrations.

.. code-block:: bash

   invenio-cli install
   pip uninstall invenio-github

----------------------------------
2. Perform the database migrations
----------------------------------

Depending on the size of your instance, the migrations can be performed either automatically by running an Alembic script, or manually by
carefully following the instructions in this guide.

If your instance meets one of these criteria, please use the manual method to avoid database stability issues:

- An ``oauthclient_remoteaccount`` table with more than 50k rows
- A ``github_repositories`` table with more than 100k rows

^^^^^^^^^^^^^^^^^^^^^^^^^^^^
2a. Automated Alembic script
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Run the upgrade command:

.. code-block:: bash

   pipenv run invenio alembic upgrade

^^^^^^^^^^^^^^^^^
2b. Manual method
^^^^^^^^^^^^^^^^^

.. SQL auto-generated from migration file using `alembic upgrade --sql`

In an SQL shell (e.g. ``psql`` for PostgreSQL), execute the following:

.. code-block:: sql

  BEGIN;
  CREATE TABLE vcs_repositories (
      id uuid NOT NULL,
      provider_id character varying(255) NOT NULL,
      name character varying(255) NOT NULL,
      hook character varying(255),
      enabled_by_user_id integer,
      created timestamp without time zone NOT NULL,
      updated timestamp without time zone NOT NULL,
      provider character varying(255) DEFAULT 'github'::character varying NOT NULL,
      default_branch character varying(255) DEFAULT 'master'::character varying NOT NULL,
      description character varying(10000),
      html_url character varying(10000) NOT NULL,
      license_spdx character varying(255)
  );
  ALTER TABLE ONLY vcs_repositories ADD CONSTRAINT pk_vcs_repositories PRIMARY KEY (id);
  ALTER TABLE ONLY vcs_repositories ADD CONSTRAINT uq_vcs_repositories_provider_name UNIQUE (provider, name);
  ALTER TABLE ONLY vcs_repositories ADD CONSTRAINT uq_vcs_repositories_provider_provider_id UNIQUE (provider, provider_id);
  ALTER TABLE ONLY vcs_repositories ADD CONSTRAINT fk_vcs_repositories_enabled_by_user_id_accounts_user FOREIGN KEY (enabled_by_user_id) REFERENCES accounts_user(id);

  CREATE TABLE vcs_releases (
      id uuid NOT NULL,
      provider_id character varying(255) NOT NULL,
      tag character varying(255),
      errors jsonb,
      repository_id uuid,
      event_id uuid,
      record_id uuid,
      status character(1) NOT NULL,
      created timestamp without time zone NOT NULL,
      updated timestamp without time zone NOT NULL,
      provider character varying(255) DEFAULT 'github'::character varying NOT NULL
  );
  ALTER TABLE ONLY vcs_releases ADD CONSTRAINT pk_vcs_releases PRIMARY KEY (id);
  ALTER TABLE ONLY vcs_releases ADD CONSTRAINT uq_vcs_releases_provider_id_provider UNIQUE (provider_id, provider);
  ALTER TABLE ONLY vcs_releases ADD CONSTRAINT uq_vcs_releases_provider_id_provider_tag UNIQUE (provider_id, provider, tag);
  CREATE INDEX ix_vcs_releases_record_id ON vcs_releases USING btree (record_id);
  ALTER TABLE ONLY vcs_releases ADD CONSTRAINT fk_vcs_releases_event_id_webhooks_events FOREIGN KEY (event_id) REFERENCES webhooks_events(id);
  ALTER TABLE ONLY vcs_releases ADD CONSTRAINT fk_vcs_releases_repository_id_vcs_repositories FOREIGN KEY (repository_id) REFERENCES vcs_repositories(id);
  COMMIT;

Next, you must perform some manual data migrations:

* The ``oauthclient_remoteaccount`` table stores the user's *entire* GitHub repository list as a dictionary within the ``extra_data`` column.
  Before the upgrade, the format is as follows:

  .. code-block:: json

    {
      "last_sync":"2025-10-15T12:30:01.027133+00:00",
      "repos": {
        "123": {
          "id": "123",
          "full_name": "org/repo",
          "description": "An example repository",
          "default_branch": "main"
        }
      }
    }

  In the new format, we no longer store repos in this JSON column. This is an inefficient approach that systems with hundreds of thousands
  of repos have outgrown.
  Previously, only *activated* repos were stored in the ``github_repositories`` table.
  Now, *all* repos are stored directly as rows of the ``vcs_repositories`` table.
  Whether or not they're activated is indicated by the presence of non-null values for the ``hook`` and ``enabled_by_user_id`` columns.

  You must perform this migration, leaving only the ``"last_sync"`` value in the ``extra_data`` JSON column.
  Not all columns of the ``vcs_repositories`` table need to be filled during the migration.
  The following columns can be left blank and will be filled during the first sync after the migration:

  * ``description``
  * ``license_spdx``

  The value for ``provider`` defaults to ``github``.

* The ``github_repositories`` table needs to be copied over to the ``vcs_repositories`` table, taking into account the changed columns.
  This should be merged with the new repos created by copying data from ``oauthclient_remoteaccount`` as shown above.

* The ``github_releases`` table needs to be copied over to the ``vcs_releases`` table.
  This can *not* be done automatically during a sync and needs to be done manually during the migration.

You can use this script as a starting point to automating these changes, but it may need some customisation depending on the size
and uptime requirements of your instance.

.. raw:: html

  <details>
    <summary>Example script</summary>

This script is non-destructive and atomic and should work for the majority of use cases, but may need slight customisation.
You can set the database connection string via the ``UPGRADE_DB`` environment variable.

.. code-block:: python

  import os
  import uuid
  from datetime import datetime, timezone

  import sqlalchemy as sa
  from sqlalchemy.dialects import postgresql
  from sqlalchemy.ext.mutable import MutableDict
  from sqlalchemy.orm import Session
  from sqlalchemy_utils import JSONType, UUIDType
  from tqdm import tqdm

  engine = sa.create_engine(os.getenv("UPGRADE_DB"), echo=False)

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
      sa.Column("provider_id", sa.String(255), nullable=True),
      sa.Column("provider", sa.String(255), nullable=True),
      sa.Column("description", sa.String(10000), nullable=True),
      sa.Column("html_url", sa.String(10000), nullable=False),
      sa.Column("license_spdx", sa.String(255), nullable=True),
      sa.Column("default_branch", sa.String(255), nullable=False),
      sa.Column("name", sa.String(255), nullable=False),
      sa.Column("hook", sa.String(255), nullable=True),
      sa.Column(
          "enabled_by_user_id", sa.Integer, sa.ForeignKey("account_user.id"), nullable=True
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
      "vcs_repositories",
      sa.Column("id", UUIDType, primary_key=True),
      sa.Column("provider_id", sa.String(255), nullable=True),
      sa.Column("provider", sa.String(255), nullable=True),
      sa.Column("tag", sa.String(255), nullable=True),
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
      sa.Column("event_id", UUIDType, sa.ForeignKey("webhooks_events.id"), nullable=True),
      sa.Column("record_id", UUIDType, nullable=True),
      sa.Column("status", sa.CHAR(1), nullable=False),
      sa.Column("created", sa.DateTime, nullable=False),
      sa.Column("updated", sa.DateTime, nullable=False),
  )

  with Session(engine) as session:

      # First, we move the JSON repos from oauthclient_remoteaccount to the new vcs_repositories table

      # We don't know the client ID as this is a config variable.
      # So to find the RemoteAccounts that correspond to GitHub, we need to check for the existence
      # of the `repos` key in the `extra_data` JSON. We cannot make this very efficient sadly, because
      # (a) in Postgres we are using JSON not JSONB so there is no efficient JSON querying and (b) the
      # instance might be using MySQL/SQLite where we store it as `TEXT`.

      remote_accounts = session.execute(sa.select(remote_account_table))
      for remote_account in tqdm(remote_accounts.mappings(), desc="remote_account"):
          if "repos" not in remote_account["extra_data"]:
              continue

          repos = remote_account["extra_data"]["repos"]

          for id, github_repo in repos.items():
              # `id` (the dict key) is a string because JSON keys must be strings

              # We might have already created it for another user
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
                        enabled_by_user_id=None,
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

      # Next, we move over any old rows from github_repositories that weren't attached to any user (for whatever reason).
      old_db_repos = session.execute(sa.select(github_repositories_table))
      for old_db_repo in tqdm(old_db_repos.mappings(), desc="repos"):
          matching_new_repo_id = session.scalar(
              sa.select(
                  vcs_repositories_table.c.id,
              ).filter_by(provider_id=str(old_db_repo["github_id"]))
          )

          if matching_new_repo_id is None:
              # We only have very limited metadata available at this point.
              # The first sync job after this migration will fill in the rest.
              session.execute(
                  vcs_repositories_table.insert().values(
                      id=old_db_repo["id"],
                      provider_id=str(old_db_repo["github_id"]),
                      provider="github",
                      name=old_db_repo["name"],
                      default_branch="main",
                      html_url=f"https://github.com/{old_db_repo["name"]}",
                      license_spdx=None,
                      hook=old_db_repo["hook"],
                      enabled_by_user_id=old_db_repo["user_id"],
                      created=old_db_repo["created"],
                      updated=datetime.now(tz=timezone.utc),
                  )
              )
          else:
              session.execute(
                  vcs_repositories_table.update()
                  .filter_by(id=matching_new_repo_id)
                  .values(
                      id=old_db_repo["id"],
                      hook=str(old_db_repo["hook"]),
                      enabled_by_user_id=old_db_repo["user_id"],
                      created=old_db_repo["created"],
                  )
              )

      # Finally, we copy over the releases
      old_db_releases = session.execute(sa.select(github_releases_table))
      for old_db_release in tqdm(old_db_releases.mappings(), desc="releases"):
          # Since we've created all the repos, we know due to referential integrity that this release's repo ID corresponds
          # to a valid and existent repo.

          session.execute(
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

      session.commit()

.. raw:: html

  </details>

Finally, once you are certain that all data has been copied over to the new tables, you can finish the migration
by running the following SQL commands:

.. code-block:: sql

   BEGIN;
   CREATE TABLE vcs_repository_users (
       repository_id UUID NOT NULL,
       user_id INTEGER NOT NULL,
       PRIMARY KEY (repository_id, user_id),
       CONSTRAINT fk_vcs_repository_users_repository_id_vcs_repositories FOREIGN KEY(repository_id) REFERENCES vcs_repositories (id),
       CONSTRAINT fk_vcs_repository_users_user_id_accounts_user FOREIGN KEY(user_id) REFERENCES accounts_user (id)
   );
   DROP TABLE github_repositories;
   DROP TABLE github_releases;
   COMMIT;

Mark the relevant migration as having been manually performed:

.. code-block:: bash

  invenio alembic stamp invenio_github@1754318294

.. note::

   The Alembic branch name ``invenio_github`` is unchanged despite all the other renamed references.
   Changing the name of an Alembic branch is not supported and would introduce too many bugs to make it
   worthwhile.
