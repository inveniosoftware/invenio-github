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
