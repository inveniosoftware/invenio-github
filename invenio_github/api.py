# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2012, 2013, 2014, 2016 CERN.
#
# Invenio is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Invenio module that adds GitHub integration to the platform."""

import github3
from flask import current_app
from invenio_db import db
from invenio_oauth2server.models import Token as ProviderToken
from invenio_oauthclient.handlers import token_getter
from invenio_oauthclient.models import RemoteAccount, RemoteToken
from invenio_oauthclient.proxies import current_oauthclient
from invenio_webhooks.proxies import current_webhooks
from werkzeug.local import LocalProxy
from werkzeug.utils import cached_property, import_string

from .models import Release, Repository
from .utils import get_extra_metadata, iso_utcnow


class GitHubAPI(object):
    """Wrapper for GitHub API."""

    def __init__(self, user_id=None):
        """Create a GitHub API object."""
        self.user_id = user_id

    @cached_property
    def api(self):
        """Return an authenticated GitHub API."""
        return github3.login(token=self.access_token)

    @cached_property
    def access_token(self):
        """Return OAuth access token."""
        if self.user_id:
            return RemoteToken.get(
                self.user_id, self.remote.consumer_key
            ).access_token
        return self.remote.get_request_token()[0]

    @property
    def session_token(self):
        """Return OAuth session token."""
        session_token = None
        if self.user_id is not None:
            session_token = token_getter(self.remote)
        if session_token:
            token = RemoteToken.get(
                self.user_id, self.remote.consumer_key,
                access_token=session_token[0]
            )
            return token
        return None

    remote = LocalProxy(
        lambda: current_oauthclient.oauth.remote_apps[
            current_app.config['GITHUB_WEBHOOK_RECEIVER_ID']
        ]
    )
    """Return OAuth remote application."""

    @cached_property
    def account(self):
        """Return remote account."""
        return RemoteAccount.get(self.user_id, self.remote.consumer_key)

    def init_account(self):
        """Setup a new GitHub account."""
        ghuser = self.api.me()
        # Setup local access tokens
        hook_token = ProviderToken.create_personal(
            'github-webhook',
            self.user_id,
            scopes=['webhooks:event'],
            is_internal=True,
        )
        # Initial structure of extra data
        self.account.extra_data = dict(
            login=ghuser.login,
            name=ghuser.name,
            tokens=dict(
                webhook=hook_token.id,
            ),
            repos=dict(),
            last_sync=iso_utcnow(),
        )
        db.session.add(self.account)
        # Fetch list of repositories
        self.sync()

    def sync(self, sync_hooks=True):
        """Synchronize user repositories."""
        account = self.account
        existing_repos = set(account.extra_data.get('repos', {}))
        new_repos = {}

        repos = self.api.repositories(type='all', sort='full_name')
        for r in repos:
            if r.permissions['admin']:
                new_repos[r.full_name] = {'description': r.description}

            # TODO synchronize hooks

        # Unassign repositories that are no longer available in GitHub.
        update_repos = existing_repos - set(new_repos.keys())
        if update_repos:
            for repo in update_repos:
                self.remove_hook(repo)
            Repository.query.filter(
                Repository.user_id == self.user_id,
                Repository.name.in_(update_repos)
            ).update(dict(user_id=None))

        # Update last sync
        account.extra_data.update(dict(
            repos=new_repos,
            last_sync=iso_utcnow(),
        ))
        account.extra_data.changed()
        db.session.add(account)

    def create_hook(self, full_name):
        """Create repository hook."""
        repository = Repository.enable(name=full_name, user_id=self.user_id)
        owner, repo = full_name.split('/')
        webhook_token = ProviderToken.query.filter_by(
            id=self.account.extra_data['tokens']['webhook']
        ).first()
        config = dict(
            url=current_webhooks.receivers[
                current_app.config['GITHUB_WEBHOOK_RECEIVER_ID']
            ].get_hook_url(webhook_token.access_token),
            content_type='json',
            secret=current_app.config['GITHUB_SHARED_SECRET'],
            insecure_ssl='1' if current_app.config['GITHUB_INSECURE_SSL']
                         else '0',
        )

        ghrepo = self.api.repository(owner, repo)
        if ghrepo:
            try:
                hook = ghrepo.create_hook(
                    'web',  # GitHub identifier for webhook service
                    config,
                    events=['release'],
                )
                if hook:
                    repository.hook = hook.id
                    return True
            except github3.GitHubError as e:
                # Check if hook is already installed
                for m in e.errors:
                    if m['code'] == 'custom' and m['resource'] == 'Hook':
                        for h in ghrepo.hooks():
                            if h.config.get('url', '') == config['url']:
                                repository.hook = hook.id
                                h.edit(
                                    config=config,
                                    events=['release'],
                                    active=True
                                )
                                return True
        return False

    def remove_hook(self, full_name):
        """Create repository hook."""
        repository = Repository.disable(name=full_name, user_id=self.user_id)
        owner, repo = full_name.split('/')

        if repository.hook:
            ghrepo = self.api.repository(owner, repo)
            if ghrepo:
                hook = ghrepo.hook(repository.hook)
                if not hook or (hook and hook.delete()):
                    repository.hook = None
                    return True
        return False


class GitHubRelease(object):
    """A GitHub release."""

    def __init__(self, event, validate=True):
        """Constructor."""
        self.event = event
        self.gh = GitHubAPI(user_id=event.user_id)

    @cached_property
    def deposit_class(self):
        """Return a class implementing `publish` method."""
        cls = current_app.config['GITHUB_DEPOSIT_CLASS']
        return cls if isinstance(cls, type) else import_string(cls)

    @cached_property
    def payload(self):
        """Return event payload."""
        return self.event.payload

    @cached_property
    def release(self):
        """Return release metadata."""
        return self.payload['release']

    @cached_property
    def repository(self):
        """Return repository metadata."""
        return self.payload['repository']

    @property
    def repository_model(self):
        """Return repository model from database."""
        return Repository.query.filter_by(
            name=self.repository['full_name'],
            enabled=True,
        ).one()

    @cached_property
    def title(self):
        """Extract title from a release."""
        if self.release['name']:
            return '{0}: {1}'.format(
                self.repository['full_name'], self.release['name']
            )
        return '{0} {1}'.format(
            self.repository['full_name'], self.release['tag_name']
        )

    @cached_property
    def description(self):
        """Extract description from a release."""
        return (
            self.gh.api.markdown(self.release['body']) or
            self.repository['description'] or
            'No description provided.'
        )

    @cached_property
    def related_identifiers(self):
        """Yield related identifiers."""
        yield dict(
            identifier='https://github.com/{0}/tree/{1}'.format(
                self.repository['full_name'], self.release['tag_name']
            ),
            relation='isSupplementTo',
        )

    @cached_property
    def defaults(self):
        """Return default metadata."""
        return dict(
            upload_type='software',
            publication_date=self.release['published_at'][:10],
            title=self.title,
            description=self.description,
            access_right='open',
            license='other-open',
            related_identifiers=[],
        )

    @cached_property
    def extra_metadata(self):
        """Get extra metadata for file in repository."""
        return get_extra_metadata(
            self.gh.api,
            self.repository['owner']['login'],
            self.repository['name'],
            self.release['tag_name'],
        ) or {}

    @cached_property
    def files(self):
        """Extract files to download from GitHub payload."""
        tag_name = self.release['tag_name']
        repo_name = self.repository['full_name']

        zipball_url = self.release['zipball_url']
        filename = '%(repo_name)s-%(tag_name)s.zip' % {
            'repo_name': repo_name, 'tag_name': tag_name
        }

        response = self.gh.api.session.head(zipball_url)
        assert response.status_code == 302, \
            'Could not retrieve archive from GitHub: {0}'.format(zipball_url)

        yield filename, zipball_url

    @property
    def metadata(self):
        """Return extracted metadata."""
        output = dict(self.defaults)
        output.update(self.extra_metadata)
        return output

    def verify_sender(self):
        """Check if the sender is valid."""
        return self.payload['repository']['full_name'] in \
            self.gh.account.extra_data['repos']

    def publish(self):
        """Publish GitHub release as record."""
        repository = self.repository_model

        with db.session.begin_nested():
            deposit = self.deposit_class.create(self.metadata)
            deposit['_deposit']['created_by'] = self.event.user_id
            deposit['_deposit']['owners'] = [self.event.user_id]

            for key, url in self.files:
                deposit.files[key] = self.gh.api.session.get(url).raw

            deposit.publish()

            repository.releases.append(Release(
                name=self.release['tag_name'],
                record=deposit.model,
                event=self.event
            ))
