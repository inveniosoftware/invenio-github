# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015, 2016 CERN.
#
# Invenio is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Invenio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio. If not, see <http://www.gnu.org/licenses/>.
#
# In applying this licence, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as an Intergovernmental Organization
# or submit itself to any jurisdiction.

"""Test cases for the badge views."""

from datetime import datetime, timedelta
from itertools import count
from types import SimpleNamespace
from uuid import uuid4

import pytest
from flask import Blueprint, url_for
from invenio_app.factory import create_api
from sqlalchemy import event

from invenio_github.models import Release, ReleaseStatus, Repository
from invenio_github.views.badge import blueprint as github_badge_blueprint

from .fixtures import TestGithubRelease

REPO_GITHUB_ID = 42
REPO_NAME = "auser/arepo"


def create_app(**kwargs):
    """Create the API application with the badge views.

    The badge views live on the UI application, whose error pages need built assets.
    """
    app = create_api(**kwargs)
    app.register_blueprint(github_badge_blueprint)
    # Same URL rule as invenio-formatter, whose real view needs ``cairosvg``.
    image_blueprint = Blueprint("invenio_formatter_badges", __name__)
    image_blueprint.add_url_rule(
        "/badge/<any(DOI):title>/<path:value>.<any(svg, png):ext>",
        "badge",
        lambda **kwargs: "",
    )
    app.register_blueprint(image_blueprint)
    return app


class ReleaseWithRecord(TestGithubRelease):
    """Reads its record the way invenio-rdm-records does.

    A deleted record keeps its ``record_id``: only reading it tells that it is gone.
    ``resolve_record`` then returns ``None`` and ``record_url`` cannot be computed.
    """

    deleted_record_ids = set()
    record_reads = []

    def resolve_record(self):
        """Return the record, or ``None`` when it is missing or deleted."""
        record_id = self.release_object.record_id
        if not record_id:
            return None
        self.record_reads.append(self.release_object.tag)
        if record_id in self.deleted_record_ids:
            return None
        doi = f"10.1234/{self.release_object.tag}"
        return SimpleNamespace(data={"links": {"doi": f"https://doi.org/{doi}"}})

    @property
    def record_url(self):
        """Return the record's DOI URL."""
        return self.record.data["links"]["doi"]

    @property
    def badge_title(self):
        """Return the badge title."""
        return "DOI"

    @property
    def badge_value(self):
        """Return the record's DOI, which stays readable after a deletion."""
        return f"10.1234/{self.release_object.tag}"


@pytest.fixture()
def release_class(app, monkeypatch):
    """Use a release class that can fail to read a deleted record."""
    monkeypatch.setattr(ReleaseWithRecord, "deleted_record_ids", set())
    monkeypatch.setattr(ReleaseWithRecord, "record_reads", [])
    monkeypatch.setattr(
        app.extensions["invenio-github"], "release_api_class", ReleaseWithRecord
    )
    return ReleaseWithRecord


@pytest.fixture()
def repo(db, test_user):
    """Create a repository owned by the test user."""
    repository = Repository.create(test_user.id, REPO_GITHUB_ID, REPO_NAME)
    db.session.commit()
    return repository


@pytest.fixture()
def add_release(db, repo, release_class):
    """Add releases to the repository, each one newer than the previous one."""
    start = datetime(2026, 1, 1)
    sequence = count(1)

    def _add(
        tag,
        record_deleted=False,
        status=ReleaseStatus.PUBLISHED,
        has_record=True,
        created=None,
    ):
        position = next(sequence)
        record_id = uuid4() if has_record else None
        if record_deleted:
            release_class.deleted_record_ids.add(record_id)
        db.session.add(
            Release(
                release_id=position,
                tag=tag,
                repository=repo,
                status=status,
                record_id=record_id,
                created=created or start + timedelta(days=position),
            )
        )
        db.session.commit()

    return _add


def _latest_doi_urls(user_id):
    """URLs that redirect to the record of the latest release."""
    return [
        url_for("invenio_github_badge.latest_doi", github_id=REPO_GITHUB_ID),
        url_for(
            "invenio_github_badge.latest_doi_old", user_id=user_id, repo_name=REPO_NAME
        ),
    ]


def _badge_image_urls(user_id):
    """URLs that redirect to the badge image of the latest release."""
    return [
        url_for("invenio_github_badge.index", repo_github_id=REPO_GITHUB_ID),
        url_for("invenio_github_badge.index_old", user_id=user_id, repo_name=REPO_NAME),
    ]


def test_latest_doi_redirects_to_latest_release(app, add_release, test_user):
    """Given two live records, the newest one wins."""
    add_release("v1")
    add_release("v2")

    with app.test_client() as client:
        for url in _latest_doi_urls(test_user.id):
            response = client.get(url)
            assert response.status_code == 302
            assert response.location == "https://doi.org/10.1234/v2"


def test_latest_doi_falls_back_to_the_previous_release(app, add_release, test_user):
    """Given a deleted newest record, the link opens the previous version."""
    add_release("v1")
    add_release("v2", record_deleted=True)

    with app.test_client() as client:
        for url in _latest_doi_urls(test_user.id):
            response = client.get(url)
            assert response.status_code == 302
            assert response.location == "https://doi.org/10.1234/v1"


def test_latest_doi_skips_releases_with_deleted_records(app, add_release, test_user):
    """Given the two newest records deleted, the link opens the one before them."""
    add_release("v1")
    add_release("v2", record_deleted=True)
    add_release("v3", record_deleted=True)

    with app.test_client() as client:
        for url in _latest_doi_urls(test_user.id):
            response = client.get(url)
            assert response.status_code == 302
            assert response.location == "https://doi.org/10.1234/v1"


def test_latest_doi_finds_live_release_tied_with_a_deleted_one(
    app, add_release, test_user
):
    """Given a deleted and a live release created together, the live one is used."""
    for position in range(5):
        add_release(f"old-{position}")
    tied = datetime(2026, 6, 1)
    add_release("tied-deleted", record_deleted=True, created=tied)
    add_release("tied-live", created=tied)

    with app.test_client() as client:
        for url in _latest_doi_urls(test_user.id):
            response = client.get(url)
            assert response.status_code == 302
            assert response.location == "https://doi.org/10.1234/tied-live"


def test_latest_doi_skips_release_without_a_record(app, add_release, test_user):
    """Given a newest release with no record, the link opens the previous version."""
    add_release("v1")
    add_release("v2", has_record=False)

    with app.test_client() as client:
        for url in _latest_doi_urls(test_user.id):
            assert client.get(url).location == "https://doi.org/10.1234/v1"


def test_latest_doi_ignores_unpublished_release(app, add_release, test_user):
    """Given a newer failed release, the last published one is used."""
    add_release("v1")
    add_release("v2", status=ReleaseStatus.FAILED)

    with app.test_client() as client:
        for url in _latest_doi_urls(test_user.id):
            assert client.get(url).location == "https://doi.org/10.1234/v1"


def test_latest_doi_returns_404_when_all_records_are_deleted(
    app, add_release, test_user
):
    """Given only deleted records, the links answer 404 rather than crashing."""
    add_release("v1", record_deleted=True)
    add_release("v2", record_deleted=True)

    with app.test_client() as client:
        for url in _latest_doi_urls(test_user.id):
            assert client.get(url).status_code == 404


def test_repository_without_published_release_returns_404(app, add_release, test_user):
    """Given only a failed release, every view answers 404."""
    add_release("v1", status=ReleaseStatus.FAILED)

    with app.test_client() as client:
        for url in _latest_doi_urls(test_user.id) + _badge_image_urls(test_user.id):
            assert client.get(url).status_code == 404


@pytest.fixture()
def release_statements(db):
    """Collect the SQL statements that read the releases table."""
    statements = []

    def record_statement(conn, cursor, statement, parameters, context, executemany):
        if "FROM github_releases" in statement:
            statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", record_statement)
    yield statements
    event.remove(db.engine, "before_cursor_execute", record_statement)


def test_latest_doi_reads_one_row_when_the_newest_record_is_live(
    app, add_release, release_class, release_statements
):
    """Given a live newest record, a single query fetches a single row."""
    for tag in ("v1", "v2", "v3"):
        add_release(tag)

    with app.test_client() as client:
        client.get(url_for("invenio_github_badge.latest_doi", github_id=REPO_GITHUB_ID))

    assert len(release_statements) == 1
    assert "LIMIT" in release_statements[0]
    assert release_class.record_reads == ["v3"]


def test_latest_doi_query_count_does_not_grow_with_deleted_records(
    app, add_release, release_class, release_statements
):
    """Given many deleted records, two queries find the release, reading each once.

    The table has no index on the repository, so each query scans all of it.
    """
    add_release("v1")
    for position in range(5):
        add_release(f"deleted-{position}", record_deleted=True)

    with app.test_client() as client:
        response = client.get(
            url_for("invenio_github_badge.latest_doi", github_id=REPO_GITHUB_ID)
        )

    assert response.location == "https://doi.org/10.1234/v1"
    assert len(release_statements) == 2
    assert release_class.record_reads == [
        "deleted-4",
        "deleted-3",
        "deleted-2",
        "deleted-1",
        "deleted-0",
        "v1",
    ]


def test_badge_image_does_not_read_the_record(
    app, release_class, add_release, test_user, monkeypatch
):
    """Given a deleted newest record, the image keeps its DOI without a record read.

    Badges are embedded in READMEs, so this path has to stay cheap.
    """

    def fail_on_read(self):
        pytest.fail("The badge image must not read the record")

    add_release("v1")
    add_release("v2", record_deleted=True)
    monkeypatch.setattr(release_class, "resolve_record", fail_on_read)

    with app.test_client() as client:
        for url in _badge_image_urls(test_user.id):
            response = client.get(url)
            assert response.status_code == 302
            assert response.location.endswith("/badge/DOI/10.1234/v2.svg")


def test_unknown_repository_returns_404(app, release_class, db):
    """Given an unknown repository, the views looking it up by itself answer 404.

    ``latest_doi_old`` is left out: it raises ``RepositoryNotFoundError`` instead, both
    before and after the deleted-record fix.
    """
    with app.test_client() as client:
        for url in (
            *_badge_image_urls(user_id=1),
            url_for("invenio_github_badge.latest_doi", github_id=REPO_GITHUB_ID),
        ):
            assert client.get(url).status_code == 404
