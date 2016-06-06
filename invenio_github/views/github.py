# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2014, 2015, 2016 CERN.
#
# Invenio is free software; you can redistribute it and/or modify
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

"""GitHub blueprint for Invenio platform.

Setting-up a public instance can take some time, hence here you can find
quite guite to test Invenio-GitHub integration.

1. Go to GitHub and create a new application.
   * Set Authorization callback URL to
     http://localhost:5000/oauth/authorized/github/
   * Add the keys to configuration:

     .. code-block: python

        GITHUB_APP_CREDENTIALS = dict(
            consumer_key='changeme',
            consumer_secret='changeme',
        )

2. Configure debug webhook receivers for GitHub:

.. code-block:: python

    WEBHOOKS_DEBUG_RECEIVER_URLS = {
        'github': 'http://github.<name>.ultrahook.com?access_token=%(token)s',
    }

3. Start Ultrahook

.. code-block:: console

    $ ultrahook github 5000/api/hooks/receivers/github/events/
"""

from __future__ import absolute_import

from datetime import datetime, timedelta

import humanize
import pytz
from dateutil.parser import parse
from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_babelex import gettext as _
from flask_breadcrumbs import register_breadcrumb
from flask_login import current_user, login_required
from flask_menu import register_menu
from invenio_db import db

from ..api import GitHubAPI
from ..helpers import check_token
from ..models import Repository
from ..utils import parse_timestamp, utcnow

blueprint = Blueprint(
    'invenio_github',
    __name__,
    static_folder='../static',
    template_folder='../templates',
    url_prefix='/account/settings/github',
)


#
# Template filters
#
@blueprint.app_template_filter('naturaltime')
def naturaltime(val):
    """Get humanized version of time."""
    val = val.replace(tzinfo=pytz.utc) \
        if isinstance(val, datetime) else parse(val)
    now = datetime.utcnow().replace(tzinfo=pytz.utc)

    return humanize.naturaltime(now - val)


#
# Views
#
@blueprint.route('/', defaults=dict(sync=False))
@blueprint.route('/sync', methods=['POST'], defaults=dict(sync=True))
@login_required
@register_menu(
    blueprint, 'settings.github',
    _('<i class="fa fa-github fa-fw"></i> GitHub'),
    order=10,
    active_when=lambda: request.endpoint.startswith('invenio_github.')
)
@register_breadcrumb(blueprint, 'breadcrumbs.settings.github', _('GitHub'))
def index(sync=False):
    """Display list of repositories."""
    github = GitHubAPI(user_id=current_user.get_id())
    token = github.session_token
    ctx = dict(connected=False)

    if token is not None and check_token(token):
        # The user is authenticated and the token we have is still valid.
        extra_data = token.remote_account.extra_data
        if extra_data.get('login') is None:
            github.init_account()
            db.session.commit()
            extra_data = token.remote_account.extra_data

        # Check if sync is needed - should probably not be done here
        now = utcnow()
        yesterday = now - timedelta(days=1)
        last_sync = parse_timestamp(extra_data['last_sync'])

        if sync or last_sync < yesterday:
            github.sync()
            db.session.commit()
            extra_data = token.remote_account.extra_data
            last_sync = parse_timestamp(extra_data['last_sync'])

        if extra_data['repos']:
            for repo in Repository.query.filter(Repository.name.in_(
                    extra_data['repos'].keys())).all():
                extra_data['repos'][repo.name]['instance'] = repo

        ctx.update({
            'connected': True,
            'repos': extra_data['repos'],
            'name': extra_data['login'],
            'user_id': token.remote_account.user_id,
            'last_sync': humanize.naturaltime(now - last_sync),
        })

    return render_template('invenio_github/settings/index.html', **ctx)


@blueprint.route('/repository/<path:name>')
@login_required
@register_breadcrumb(blueprint, 'breadcrumbs.settings.github.repo', _('Repo'))
def repository(name):
    """Display selected repository."""
    github = GitHubAPI(user_id=current_user.get_id())
    token = github.session_token
    ctx = dict(connected=False)

    if token is not None and check_token(token):
        extra_data = github.account.extra_data
        if name not in extra_data['repos']:
            abort(403)

        repo = Repository.query.filter_by(name=name).first()
        return render_template('invenio_github/settings/view.html', repo=repo)

    abort(403)


@blueprint.route('/faq')
@login_required
def faq():
    """Display FAQ."""
    return render_template('invenio_github/settings/faq.html')


@blueprint.route('/rejected')
@login_required
def rejected():
    """View for when user rejects request to connect to github."""
    return render_template('invenio_github/settings/rejected.html')


@blueprint.route('/hook', methods=['POST', 'DELETE'])
@login_required
def hook():
    """Install or remove GitHub webhook."""
    repo = request.json['repo']
    github = GitHubAPI(user_id=current_user.get_id())

    if repo not in github.account.extra_data['repos']:
        abort(404)

    if request.method == 'DELETE':
        if github.remove_hook(repo):
            db.session.commit()
            return '', 204
        else:
            abort(400)
    elif request.method == 'POST':
        if github.create_hook(repo):
            db.session.commit()
            return '', 201
        else:
            abort(400)
    else:
        abort(400)


@blueprint.route('/hook/<action>/<path:repo>')
@login_required
def hook_action(action, repo):
    """Display selected repository."""
    github = GitHubAPI(user_id=current_user.get_id())

    if repo not in github.account.extra_data['repos']:
        abort(404)

    if action == 'disable':
        if github.remove_hook(repo):
            db.session.commit()
            return redirect(url_for('.index'))
        else:
            abort(400)
    elif action == 'enable':
        if github.create_hook(repo):
            db.session.commit()
            return redirect(url_for('.index'))
        else:
            abort(400)
    else:
        abort(400)
