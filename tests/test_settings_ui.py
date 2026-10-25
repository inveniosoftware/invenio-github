# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 CERN.
#
# Invenio-Github is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""Test the GitHub settings page markup that the frontend relies on."""

from html.parser import HTMLParser

import pytest
from flask import Blueprint
from invenio_accounts.testutils import login_user_via_session
from invenio_app.factory import create_ui
from invenio_db import db

from invenio_github.api import GitHubAPI

# The settings page is served by the UI application (see pytest-invenio base_app).
create_app = create_ui


class _NoAssetsManifest:
    """Render no script/style tags: webpack assets are not built in tests."""

    def __getitem__(self, entry):
        return ""

    def __getattr__(self, entry):
        return ""


class _NoAssetsManifestLoader:
    def load(self, filepath):
        return _NoAssetsManifest()


@pytest.fixture(scope="module")
def app_config(app_config):
    """Render the semantic-ui settings templates without built assets."""
    app_config["APP_THEME"] = ["semantic-ui"]
    app_config["WEBPACKEXT_MANIFEST_LOADER"] = _NoAssetsManifestLoader
    return app_config


@pytest.fixture(scope="module")
def app(app):
    """Stand in for the invenio-formatter badges blueprint.

    The real one needs ``cairosvg``, which is not a test dependency; the page only
    needs its URL rule and its macro templates.
    """
    badges = Blueprint(
        "invenio_formatter_badges", "invenio_formatter", template_folder="templates"
    )
    badges.add_url_rule(
        "/badge/<title>/<path:value>.<ext>", "badge", lambda **kwargs: ""
    )
    app.register_blueprint(badges)
    return app


class _SettingsPage(HTMLParser):
    """Where each element and repository of the page sits.

    Records, for every element, whether it is inside the ``#github-repositories``
    container that the frontend re-renders, and in which list section.
    """

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link"}
    VOID |= {"meta", "source", "track", "wbr"}

    def __init__(self, html):
        super().__init__()
        self.stack = []
        self.elements = []
        self.repositories = {}
        self.feed(html)

    def _context(self):
        in_lists = any(a.get("id") == "github-repositories" for _, a in self.stack)
        sections = [a["aria-label"] for t, a in self.stack if t == "section"]
        return in_lists, sections[-1] if sections else None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        in_lists, section = self._context()
        self.elements.append((tag, attrs, in_lists, section))
        if tag not in self.VOID:
            self.stack.append((tag, attrs))

    def handle_endtag(self, tag):
        if tag in self.VOID or tag not in [t for t, _ in self.stack]:
            return
        while self.stack.pop()[0] != tag:
            pass

    def handle_data(self, data):
        if self.stack and self.stack[-1][0] == "b" and data.strip():
            self.repositories[data.strip()] = self._context()

    def find(self, id=None, cls=None, attr=None):
        """Return ``(in_lists, section)`` of every matching element."""
        return [
            (in_lists, section)
            for _, attrs, in_lists, section in self.elements
            if (id is None or attrs.get("id") == id)
            and (cls is None or cls in (attrs.get("class") or "").split())
            and (attr is None or attr in attrs)
        ]


def _render_settings_page(client, user):
    login_user_via_session(client, email=user.email)
    res = client.get("/account/settings/github/")
    assert res.status_code == 200
    return res.get_data(as_text=True)


def test_settings_page_renders_what_the_frontend_selects(
    app, client, github_api, test_user
):
    """Every id and class index.js relies on is rendered where it expects it."""
    api = GitHubAPI(test_user.id)
    api.init_account()
    api.sync()
    db.session.commit()

    page = _SettingsPage(_render_settings_page(client, test_user))

    assert len(page.find(id="github-repositories")) == 1
    # Outside the re-rendered lists: the sync controls and the last sync text.
    for id in [
        "sync_repos",
        "sync_repos_btn_text",
        "loader_icon",
        "sync-result-message",
        "sync_repos_help_text",
    ]:
        assert page.find(id=id) == [(False, "GitHub Repositories")], id
    # Inside them: one item, switch and message per repository.
    for selector in [
        {"cls": "repository-item"},
        {"cls": "repo-switch-message"},
        {"attr": "data-repo-id"},
    ]:
        assert page.find(**selector) == [(True, "Repositories")] * 3, selector


def test_settings_page_splits_repositories_by_hook(app, client, github_api, test_user):
    """An enabled repository is listed under "Enabled Repositories" only."""
    api = GitHubAPI(test_user.id)
    api.init_account()
    api.sync()
    api.create_hook(1, "auser/repo-1")
    db.session.commit()

    page = _SettingsPage(_render_settings_page(client, test_user))

    assert page.repositories == {
        "auser/repo-1": (True, "Enabled Repositories"),
        "auser/repo-2": (True, "Repositories"),
        "auser/arepo": (True, "Repositories"),
    }
