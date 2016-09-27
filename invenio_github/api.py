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
from invenio_pidstore.proxies import current_pidstore
from mistune import markdown
from six import string_types
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.local import LocalProxy
from werkzeug.utils import cached_property, import_string

from .errors import RepositoryAccessError
from .models import Repository
from .tasks import sync_hooks
from .utils import get_extra_metadata, iso_utcnow, parse_timestamp, utcnow


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

    @cached_property
    def webhook_url(self):
        """Return the url to be used by a GitHub webhook."""
        webhook_token = ProviderToken.query.filter_by(
            id=self.account.extra_data['tokens']['webhook']
        ).first()
        if webhook_token:
            wh_url = current_app.config.get('GITHUB_WEBHOOK_RECEIVER_URL')
            if wh_url:
                return wh_url.format(token=webhook_token.access_token)
            else:
                raise RuntimeError('You must set GITHUB_WEBHOOK_RECEIVER_URL.')

    def init_account(self):
        """Setup a new GitHub account."""
        ghuser = self.api.me()
        # Setup local access tokens to be used by the webhooks
        hook_token = ProviderToken.create_personal(
            'github-webhook',
            self.user_id,
            scopes=['webhooks:event'],
            is_internal=True,
        )
        # Initial structure of extra data
        self.account.extra_data = dict(
            id=ghuser.id,
            login=ghuser.login,
            name=ghuser.name,
            tokens=dict(
                webhook=hook_token.id,
            ),
            repos=dict(),
            last_sync=iso_utcnow(),
        )
        db.session.add(self.account)

        # Sync data from GitHub, but don't check repository hooks yet.
        self.sync(hooks=False)

    def sync(self, hooks=True, async_hooks=True):
        """Synchronize user repositories.

        :param bool hooks: True for syncing hooks.
        :param bool async_hooks: True for sending of an asynchronous task to
                                 sync hooks.

        .. note::

            Syncing happens from GitHub's direction only. This means that we
            consider the information on GitHub as valid, and we overwrite our
            own state based on this information.
        """
        active_repos = {}
        github_repos = {repo.id: repo for repo in self.api.repositories()
                        if repo.permissions['admin']}
        for gh_repo_id, gh_repo in github_repos.items():
            active_repos[gh_repo_id] = {
                'id': gh_repo_id,
                'full_name': gh_repo.full_name,
                'description': gh_repo.description,
            }

        if hooks:
            self._sync_hooks(list(active_repos.keys()), async=async_hooks)

        # Remove ownership from repositories that the user has no longer
        # 'admin' permissions, or have been deleted.
        Repository.query.filter(
            Repository.user_id == self.user_id,
            ~Repository.github_id.in_(github_repos.keys())
        ).update(dict(user_id=None, hook=None), synchronize_session=False)

        # Update repos and last sync
        self.account.extra_data.update(dict(
            repos=active_repos,
            last_sync=iso_utcnow(),
        ))
        self.account.extra_data.changed()
        db.session.add(self.account)

    def _sync_hooks(self, repos, async=True):
        """Check if a hooks sync task needs to be started."""
        if not async:
            for repo_id in repos:
                try:
                    with db.session.begin_nested():
                        self.sync_repo_hook(repo_id)
                    db.session.commit()
                except (NoResultFound, RepositoryAccessError) as e:
                    current_app.logger.warning(e.message, exc_info=True)
        else:
            # FIXME: We have to commit, in order to have all necessary data?
            db.session.commit()
            sync_hooks.delay(self.user_id, repos)

    def sync_repo_hook(self, repo_id):
        """Sync a GitHub repo's hook with the locally stored repo."""
        # Get the hook that we may have set in the past
        gh_repo = self.api.repository_with_id(repo_id)
        hooks = (hook.id for hook in gh_repo.hooks()
                 if hook.config.get('url', '') == self.webhook_url)
        hook_id = next(hooks, None)

        # If hook on GitHub exists, get or create corresponding db object and
        # enable the hook. Otherwise remove the old hook information.
        if hook_id:
            Repository.enable(user_id=self.user_id,
                              github_id=gh_repo.id,
                              name=gh_repo.full_name,
                              hook=hook_id)
        else:
            Repository.disable(user_id=self.user_id,
                               github_id=gh_repo.id,
                               name=gh_repo.full_name)

    def check_sync(self):
        """Check if sync is required based on last sync date."""
        # If refresh interval is not specified, we should refresh every time.
        expiration = utcnow()
        refresh_td = current_app.config.get('GITHUB_REFRESH_TIMEDELTA')
        if refresh_td:
            expiration -= refresh_td
        last_sync = parse_timestamp(self.account.extra_data['last_sync'])
        return last_sync < expiration

    def create_hook(self, repo_id, repo_name):
        """Create repository hook."""
        config = dict(
            url=self.webhook_url,
            content_type='json',
            secret=current_app.config['GITHUB_SHARED_SECRET'],
            insecure_ssl='1' if current_app.config['GITHUB_INSECURE_SSL']
                         else '0',
        )

        ghrepo = self.api.repository_with_id(repo_id)
        if ghrepo:
            try:
                hook = ghrepo.create_hook(
                    'web',  # GitHub identifier for webhook service
                    config,
                    events=['release'],
                )
            except github3.GitHubError as e:
                # Check if hook is already installed
                hook_errors = (m for m in e.errors
                               if m['code'] == 'custom' and
                               m['resource'] == 'Hook')
                if next(hook_errors, None):
                    hooks = (h for h in ghrepo.hooks()
                             if h.config.get('url', '') == config['url'])
                    hook = next(hooks, None)
                    if hook:
                        hook.edit(config=config, events=['release'])
            finally:
                if hook:
                    Repository.enable(user_id=self.user_id,
                                      github_id=repo_id,
                                      name=repo_name,
                                      hook=hook.id)
                    return True
        return False

    def remove_hook(self, repo_id, name):
        """Remove repository hook."""
        ghrepo = self.api.repository_with_id(repo_id)
        if ghrepo:
            hooks = (h for h in ghrepo.hooks()
                     if h.config.get('url', '') == self.webhook_url)
            hook = next(hooks, None)
            if not hook or hook.delete():
                Repository.disable(user_id=self.user_id,
                                   github_id=repo_id,
                                   name=name)
                return True
        return False

    @classmethod
    def _dev_api(cls):
        """Get a developer instance for GitHub API access."""
        gh = github3.GitHub()
        gh.set_client_id(cls.remote.consumer_key, cls.remote.consumer_secret)
        return gh

    @classmethod
    def check_token(cls, token):
        """Check if an access token is authorized."""
        return cls._dev_api().check_authorization(token)

    @classmethod
    def revoke_token(cls, token):
        """Revoke an access token."""
        return cls._dev_api().revoke_authorization(token)


class GitHubRelease(object):
    """A GitHub release."""

    def __init__(self, release):
        """Constructor."""
        self.model = release

    @cached_property
    def gh(self):
        """Return GitHubAPI object."""
        return GitHubAPI(user_id=self.event.user_id)

    @cached_property
    def deposit_class(self):
        """Return a class implementing `publish` method."""
        cls = current_app.config['GITHUB_DEPOSIT_CLASS']
        if isinstance(cls, string_types):
            cls = import_string(cls)
        assert isinstance(cls, type)
        return cls

    @cached_property
    def event(self):
        """Get release event."""
        return self.model.event

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
    def repo_model(self):
        """Return repository model from database."""
        return Repository.query.filter_by(
            user_id=self.event.user_id,
            github_id=self.repository['id'],
        ).one()

    @cached_property
    def title(self):
        """Extract title from a release."""
        if self.event:
            if self.release['name']:
                return u'{0}: {1}'.format(
                    self.repository['full_name'], self.release['name']
                )
        return u'{0} {1}'.format(self.repo_model.name, self.model.tag)

    @cached_property
    def description(self):
        """Extract description from a release."""
        if self.release.get('body'):
            return markdown(self.release['body'])
        elif self.repository.get('description'):
            return self.repository['description']
        return 'No description provided.'

    @cached_property
    def author(self):
        """Extract the author's GitHub username from a release."""
        return self.release.get('author', {}).get('login')

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
            access_right='open',
            description=self.description,
            license='other-open',
            publication_date=self.release['published_at'][:10],
            related_identifiers=list(self.related_identifiers),
            title=self.title,
            upload_type='software',
        )

    @cached_property
    def extra_metadata(self):
        """Get extra metadata for file in repository."""
        return get_extra_metadata(
            self.gh.api,
            self.repository['owner']['login'],
            self.repository['name'],
            self.release['tag_name'],
        )

    @cached_property
    def files(self):
        """Extract files to download from GitHub payload."""
        tag_name = self.release['tag_name']
        repo_name = self.repository['full_name']

        zipball_url = self.release['zipball_url']
        filename = '{name}-{tag}.zip'.format(name=repo_name, tag=tag_name)

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

    @cached_property
    def record(self):
        """Get Release record."""
        return self.model.record

    @cached_property
    def pid(self):
        """Get PID object for the Release record."""
        if self.record:
            fetcher = current_pidstore.fetchers[
                current_app.config.get('GITHUB_PID_FETCHER')]
            return fetcher(self.record.id, self.record)

    def verify_sender(self):
        """Check if the sender is valid."""
        return self.payload['repository']['full_name'] in \
            self.gh.account.extra_data['repos']

    def publish(self):
        """Publish GitHub release as record."""
        with db.session.begin_nested():
            deposit = self.deposit_class.create(self.metadata)
            deposit['_deposit']['created_by'] = self.event.user_id
            deposit['_deposit']['owners'] = [self.event.user_id]

            # Fetch the deposit files
            for key, url in self.files:
                deposit.files[key] = self.gh.api.session.get(
                    url, stream=True).raw

            deposit.publish()
            self.model.recordmetadata = deposit.model
