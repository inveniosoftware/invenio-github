# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016 CERN.
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


"""Test CLI for GitHub."""

from __future__ import absolute_import, print_function

import pytest
from mock import patch

from invenio_github.api import GitHubAPI


def test_hook_sync(app, cli_run, tester_id):
    """Test 'hook sync' CLI."""
    # Test with user's email
    with patch.object(GitHubAPI, 'sync') as mock_obj:
        ret = cli_run('hook sync info@inveniosoftware.org')
    assert ret.exit_code == 0
    assert ret.output == ''
    mock_obj.assert_called_once_with(hooks=False, async_hooks=False)

    # Test call with user ID
    with patch.object(GitHubAPI, 'sync') as mock_obj:
        ret = cli_run('hook sync {0}'.format(tester_id))
    assert ret.exit_code == 0
    assert ret.output == ''
    mock_obj.assert_called_once_with(hooks=False, async_hooks=False)

    # Test call with flags
    with patch.object(GitHubAPI, 'sync') as mock_obj:
        ret = cli_run('hook sync info@inveniosoftware.org --hooks True'
                      ' --async-hooks=True')
    assert ret.exit_code == 0
    assert ret.output == ''
    mock_obj.assert_called_once_with(hooks=True, async_hooks=True)


def test_hook_create(app, cli_run, users, repositories):
    """Test 'hook create' CLI."""
    with patch.object(GitHubAPI, 'create_hook') as mock_obj:
        ret = cli_run('hook create u1@foo.bar foo/bar --yes-i-know')
    assert ret.exit_code == 0
    assert ret.output.startswith('Hook is already installed for')
    assert not mock_obj.called

    repo = repositories[1]  # baz/spam repository
    with patch.object(GitHubAPI, 'create_hook') as mock_obj:
        ret = cli_run('hook create u1@foo.bar baz/spam --yes-i-know')
    assert ret.exit_code == 0
    assert ret.output == ''
    mock_obj.assert_called_once_with(repo['github_id'], repo['name'])

    with patch.object(GitHubAPI, 'create_hook') as mock_obj:
        ret = cli_run('hook create u1@foo.bar {0} --yes-i-know'.format(
            repo['github_id']))
    assert ret.output == ''
    assert ret.exit_code == 0
    mock_obj.assert_called_once_with(repo['github_id'], repo['name'])


def test_hook_remove(app, cli_run, users, repositories):
    """Test 'hook remove' CLI."""
    repo0 = repositories[0]  # foo/bar repository, owned by u1
    repo1 = repositories[1]  # baz/spam repository, orphaned

    # Remove hook from an 'enabled' repo without a user
    with patch.object(GitHubAPI, 'remove_hook') as mock_obj:
        ret = cli_run('hook remove foo/bar --yes-i-know')
    assert ret.exit_code == 0
    assert ret.output == ''
    mock_obj.assert_called_once_with(repo0['github_id'], repo0['name'])

    # Remove hook from an 'enabled' repo with owner specified
    with patch.object(GitHubAPI, 'remove_hook') as mock_obj:
        ret = cli_run('hook remove foo/bar -u u1@foo.bar --yes-i-know')
    assert ret.exit_code == 0
    assert ret.output == ''
    mock_obj.assert_called_once_with(repo0['github_id'], repo0['name'])

    # Remove hook from an 'enabled' repo with non-owner specified
    with patch.object(GitHubAPI, 'remove_hook') as mock_obj:
        ret = cli_run('hook remove foo/bar -u u2@foo.bar --yes-i-know')
    assert ret.exit_code == 0
    assert ret.output == \
        'Warning: Specified user is not the owner of this repository.\n'
    mock_obj.assert_called_once_with(repo0['github_id'], repo0['name'])

    # Remove hook from an orphaned repo without specifying a user
    with patch.object(GitHubAPI, 'remove_hook') as mock_obj:
        ret = cli_run('hook remove baz/spam --yes-i-know')
    assert ret.exit_code == 0
    assert ret.output == \
        "Repository doesn't have an owner, please specify a user.\n"
    assert not mock_obj.called

    # Remove hook from an orphaned repo with user specified
    with patch.object(GitHubAPI, 'remove_hook') as mock_obj:
        ret = cli_run('hook remove baz/spam -u u1@foo.bar --yes-i-know')
    assert ret.exit_code == 0
    assert ret.output == 'Warning: Repository is not owned by any user.\n'
    mock_obj.assert_called_once_with(repo1['github_id'], repo1['name'])


def test_repo_list(app, cli_run, users, repositories, remoteaccounts):
    """Test 'repo list' CLI."""
    # List repos 'owned' by the user
    ret = cli_run('repo list u1@foo.bar')
    assert ret.exit_code == 0
    assert ret.output.startswith('User has 2 enabled repositories.')
    assert 'foo/bar:8000' in ret.output
    assert 'bacon/eggs:8002' in ret.output
    assert 'other/repo:8003' not in ret.output

    # List repos including the list from extra_data
    ret = cli_run('repo list u1@foo.bar --all')
    assert ret.exit_code == 0
    assert ret.output.startswith('User has 3 repositories in total.')
    assert 'foo/bar:8000' in ret.output
    assert 'bacon/eggs:8002' in ret.output
    assert 'other/repo:8003' in ret.output


@patch.object(GitHubAPI, 'remove_hook')
@patch.object(GitHubAPI, 'create_hook')
def test_repo_move(ch_mock, rh_mock, app, cli_run, users, repositories):
    """Test 'repo move' CLI."""
    ret = cli_run('repo move u2@foo.bar -r 8000 --yes-i-know')
    assert ret.exit_code == 0
    rh_mock.assert_called_once_with(8000, 'foo/bar')
    ch_mock.assert_called_once_with(8000, 'foo/bar')


@pytest.mark.parametrize('u2', ['u2@foo.bar', '2'])
@pytest.mark.parametrize('r1', ['foo/bar', '8000'])
@pytest.mark.parametrize('r2', ['bacon/eggs', '8002'])
@patch.object(GitHubAPI, 'remove_hook')
@patch.object(GitHubAPI, 'create_hook')
def test_repo_move_repos(ch_mock, rh_mock, r2, r1, u2, app, cli_run,
                         users, repositories):
    """Test 'repo move' CLI."""
    # Make sure the 'u2' parameter is correct
    assert users[1]['email'] == 'u2@foo.bar'
    assert users[1]['id'] == 2
    cmd = 'repo move {0} --repo {1} -r {2} --yes-i-know'.format(u2, r1, r2)
    ret = cli_run(cmd)
    assert ret.exit_code == 0
    rh_mock.call_count == 2
    ch_mock.call_count == 2
    rh_mock.assert_any_call(8000, 'foo/bar')
    rh_mock.assert_any_call(8002, 'bacon/eggs')
    ch_mock.assert_any_call(8000, 'foo/bar')
    ch_mock.assert_any_call(8002, 'bacon/eggs')


@pytest.mark.parametrize('u1', ['u1@foo.bar', '1'])
@pytest.mark.parametrize('u2', ['u2@foo.bar', '2'])
@pytest.mark.parametrize('allof', ['--all-of-user', '-A'])
@patch.object(GitHubAPI, 'remove_hook')
@patch.object(GitHubAPI, 'create_hook')
def test_repo_move_allof(ch_mock, rh_mock, u1, u2, allof, app, cli_run, users,
                         repositories):
    """Test 'repo move' CLI."""
    # Make sure the 'u1' and 'u2' parameters are correct
    assert users[0]['email'] == 'u1@foo.bar'
    assert users[0]['id'] == 1
    assert users[1]['email'] == 'u2@foo.bar'
    assert users[1]['id'] == 2
    # 'repo move {u2@foo.bar,2} {--all-of-user,-A} {u1@foo.bar,1} --yes-i-know'
    cmd = 'repo move {0} {1} {2} --yes-i-know'.format(u2, allof, u1)
    ret = cli_run(cmd)
    assert ret.exit_code == 0
    rh_mock.call_count == 2
    ch_mock.call_count == 2
    rh_mock.assert_any_call(8000, 'foo/bar')
    rh_mock.assert_any_call(8002, 'bacon/eggs')
    ch_mock.assert_any_call(8000, 'foo/bar')
    ch_mock.assert_any_call(8002, 'bacon/eggs')
