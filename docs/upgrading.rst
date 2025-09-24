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

.. code-block:: sql

   BEGIN;
   ALTER TABLE github_repositories RENAME TO vcs_repositories;
   ALTER TABLE vcs_repositories ALTER COLUMN github_id TYPE VARCHAR(255);
   ALTER TABLE vcs_repositories ALTER COLUMN github_id SET NOT NULL;
   ALTER TABLE vcs_repositories RENAME github_id TO provider_id;
   ALTER TABLE vcs_repositories ALTER COLUMN hook TYPE VARCHAR(255);
   ALTER TABLE vcs_repositories ALTER COLUMN hook DROP NOT NULL;
   ALTER TABLE vcs_repositories ADD COLUMN provider VARCHAR(255) DEFAULT 'github' NOT NULL;
   ALTER TABLE vcs_repositories ADD COLUMN default_branch VARCHAR(255) DEFAULT 'master' NOT NULL;
   ALTER TABLE vcs_repositories ADD COLUMN description VARCHAR(10000);
   ALTER TABLE vcs_repositories ADD COLUMN html_url VARCHAR(10000);
   ALTER TABLE vcs_repositories ADD COLUMN license_spdx VARCHAR(255);
   ALTER TABLE vcs_repositories RENAME user_id TO enabled_by_id;
   DROP INDEX ix_github_repositories_name;
   DROP INDEX ix_github_repositories_github_id;
   ALTER TABLE vcs_repositories ADD CONSTRAINT uq_vcs_repositories_provider_provider_id UNIQUE (provider, provider_id);
   ALTER TABLE vcs_repositories ADD CONSTRAINT uq_vcs_repositories_provider_name UNIQUE (provider, name);
   COMMIT;

Do some things here

.. code-block:: sql

   BEGIN;
   ALTER TABLE vcs_repositories ALTER COLUMN html_url SET NOT NULL;
   ALTER TABLE github_releases RENAME TO vcs_releases;
   ALTER TABLE vcs_releases ALTER COLUMN release_id TYPE VARCHAR(255);
   ALTER TABLE vcs_releases ALTER COLUMN release_id SET NOT NULL;
   ALTER TABLE vcs_releases RENAME release_id TO provider_id;
   ALTER TABLE vcs_releases ADD COLUMN provider VARCHAR(255) DEFAULT 'github' NOT NULL;
   ALTER TABLE vcs_releases ALTER COLUMN errors TYPE JSONB USING errors::text::jsonb;
   ALTER TABLE vcs_releases DROP CONSTRAINT uq_github_releases_release_id;
   ALTER TABLE vcs_releases ADD CONSTRAINT uq_vcs_releases_provider_id_provider UNIQUE (provider_id, provider);
   ALTER TABLE vcs_releases ADD CONSTRAINT uq_vcs_releases_provider_id_provider_tag UNIQUE (provider_id, provider, tag);
   CREATE TABLE vcs_repository_users (
       repository_id UUID NOT NULL,
       user_id INTEGER NOT NULL,
       PRIMARY KEY (repository_id, user_id),
       CONSTRAINT fk_vcs_repository_users_repository_id_vcs_repositories FOREIGN KEY(repository_id) REFERENCES vcs_repositories (id),
       CONSTRAINT fk_vcs_repository_users_user_id_accounts_user FOREIGN KEY(user_id) REFERENCES accounts_user (id)
   );
   COMMIT;
