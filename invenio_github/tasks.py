# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2014, 2015, 2016 CERN.
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

"""Task for managing GitHub integration."""

from __future__ import absolute_import

import json

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from flask import current_app
from invenio_db import db


# FIXME: If we don't call disconnect_github.retry() somewhere, we're not
# actually retrying the task!
@shared_task(max_retries=6, default_retry_delay=10 * 60, rate_limit='100/m')
def disconnect_github(access_token, repo_hooks):
    """Uninstall webhooks."""
    # Note at this point the remote account and all associated data have
    # already been deleted. The celery task is passed the access_token to make
    # some last cleanup and afterwards delete itself remotely.
    import github3
    from .api import GitHubAPI

    try:
        gh = github3.login(token=access_token)
        for repo_id, repo_hook in repo_hooks:
            ghrepo = gh.repository_with_id(repo_id)
            if ghrepo:
                hook = ghrepo.hook(repo_hook)
                if hook and hook.delete():
                    info_msg = 'Deleted hook {hook} from {repo}'.format(
                        hook=hook.id, repo=ghrepo.full_name)
                    current_app.logger.info(info_msg)
    except MaxRetriesExceededError:
        # FIXME: Log the 'access_token' here? Or is it available on Celery?
        err_msg = ('Could not completely clean-up GitHub remote account for '
                   'user {0}'.format(user=gh.me().name))
        current_app.logger.error(err_msg)
    except Exception as exc:
        # Retry in case GitHub may be down...
        raise disconnect_github.retry(exc=exc)

    # If we finished our clean-up successfully, we can revoke the token
    GitHubAPI.revoke_token(access_token)


@shared_task(max_retries=6, default_retry_delay=10 * 60, rate_limit='100/m')
def sync_hooks(user_id, repositories):
    """Sync repository hooks for a user."""
    from .api import GitHubAPI

    try:
        # Sync hooks
        gh = GitHubAPI(user_id=user_id)
        for repo_id in repositories:
            with db.session.begin_nested():
                gh.sync_repo_hook(repo_id)
            # FIXME: Commit once per repository, or only at the end?
            db.session.commit()
    except Exception as exc:
        raise sync_hooks.retry(exc=exc)


@shared_task(ignore_result=True)
def process_release(release_id, verify_sender=False):
    """Process a received Release."""
    from .models import Release, ReleaseStatus
    from .proxies import current_github
    # from github3.exceptions import GitHubError
    from invenio_db import db
    from invenio_rest.errors import RESTException

    # Get the Release model from the database
    release_model = Release.query.filter(
        Release.release_id == release_id,
        Release.status.in_([ReleaseStatus.RECEIVED, ReleaseStatus.FAILED]),
    ).one()
    release_model.status = ReleaseStatus.PROCESSING
    db.session.commit()

    release = current_github.release_api_class(release_model)
    if verify_sender and not release.verify_sender():
        raise Exception('Invalid sender for payload %s for user %s' % (
            release.event.payload, release.event.user_id
        ))

    try:
        release.publish()
        release.release_model.status = ReleaseStatus.PUBLISHED
    except RESTException as rest_ex:
        current_app.logger.exception("Error while processing GitHub Release")
        release.release_model.errors = json.loads(rest_ex.get_body())
        release.release_model.status = ReleaseStatus.FAILED
    # FIXME: We may want to handle GitHub errors differently in the future
    # except GitHubError as github_ex:
    #     current_app.logger.exception("Error while processing GitHub Release")
    #     release.release_model.errors = {'error': str(e)}
    #     release.release_model.status = ReleaseStatus.FAILED
    except Exception:
        current_app.logger.exception("Error while processing GitHub Release")
        release.release_model.errors = {'errors': "Unknown error occured."}
        release.release_model.status = ReleaseStatus.FAILED
    finally:
        db.session.commit()
