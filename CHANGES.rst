..
    This file is part of Invenio.
    Copyright (C) 2016-2024 CERN.
    Copyright (C) 2024-2025 Graz University of Technology.

    Invenio is free software; you can redistribute it
    and/or modify it under the terms of the GNU General Public License as
    published by the Free Software Foundation; either version 2 of the
    License, or (at your option) any later version.

    Invenio is distributed in the hope that it will be
    useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Invenio; if not, write to the
    Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
    MA 02111-1307, USA.

    In applying this license, CERN does not
    waive the privileges and immunities granted to it by virtue of its status
    as an Intergovernmental Organization or submit itself to any jurisdiction.


Changes
=======

Version 3.0.0 (release 2025-06-03)

- setup: bump major dependencies
- fix: setuptools require underscores instead of dashes
- i18n: update string formatting for compatibility
- i18n: mark strings for translation

Version 2.0.0 (release 2024-12-12)

- comp: make compatible to flask-sqlalchemy>=3.1
- setup: bump major dependencies

Version 1.5.4 (released 2024-12-12)

- fix: publish with translations

Version 1.5.3 (release 2024-11-29)

- setup: change to reusable workflows
- setup: pin dependencies

Version v1.5.2 (released 2024-08-15)

- api: fix repository sync by organization users

Version v1.5.1 (released 2024-03-24)

- init: register menu only if GH integration is enabled (bugfix)

Version v1.5.0 (released 2024-03-23)

- Changed uritemplate-py dependency to uritemplate
- i18n: fix transifex config
- i18n: add transifex workflows
- global: move to finalize_app

Version v1.4.0 (released 2024-01-24)

- api: added session timeout to fetch zipball

Version v1.3.1 (released 2023-11-13)

- oauth: remove uneccessary `user` scope.

Version v1.3.0 (released 2023-10-25)

- api: change permission calculation

Version v1.2.1 (released 2023-10-23)

- tasks: added sentry event id for custom errors.
- release: fetch owner from remote.

Version v1.2.0 (released 2023-10-20)

- badges: remove permission check for index view

Version v1.1.1 (released 2023-10-20)

- badges: remove user_id check from old endpoint
- ui: fixed rendering of releases without event

Version v1.1.0 (released 2023-10-19)

- config: added default configs for citation cff support.

Version v1.0.13 (released 2023-10-17)

- api: fix contributor iterator

Version v1.0.12 (released 2023-10-17)

- api: fetch contributors by authenticated api
- view: fixed wrong accesses to event.payload

Version v1.0.11 (released 2023-10-16)

- badge: fix expected DOI type

Version v1.0.10 (released 2023-10-14)

- badge: fix expected pid object

Version v1.0.9 (released 2023-10-14)

- views: read correct record id

Version v1.0.8 (released 2023-10-13)

- api: fix permission check

Version v1.0.7 (released 2023-10-13)

- models: fix repositories fetching

Version v1.0.6 (released 2023-10-13)

- badge: fix config class

Version v1.0.5 (released 2023-10-12)

- assets: increase timeout on sync repos

Version v1.0.4 (released 2023-10-11)

- api: remove catch all block on contributors of release

Version v1.0.3 (released 2023-10-11)

- view: fix badge fetch by PID
- assets: fix timeout on long requests

Version v1.0.2 (released 2023-07-26)

- api: fix csrf errors on API

Version v1.0.1 (released 2023-07-26)

- ui: layout and styling improvements

Version v1.0.0 (released 2023-07-24)

- inital public release

Version v1.0.0b7 (released 2023-07-24)

- handlers: fix oauthclient import

Version v1.0.0b6 (released 2023-07-21)

- add github badges

Version v1.0.0b5 (released 2023-07-17)

- setup: enable tests
- setup: update Manifest.in

Version v1.0.0b4 (released 2023-07-17)

- alembic: add webhook dependency in alembic recipes

Version v1.0.0b3 (released 2023-07-17)

- alembic: add alembic recipes

Version v1.0.0b2 (released 2023-07-17)

- global: restrain extension behind feature flag
- api: add record serialization
- handlers: fix hooks serialization

Version v1.0.0b1 (released 2023-07-03)

- Initial beta release.

Version v1.0.0a28 (released 2022-10-24)

- Initial public release.
