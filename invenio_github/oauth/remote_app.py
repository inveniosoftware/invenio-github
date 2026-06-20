# SPDX-FileCopyrightText: 2023 CERN.
# SPDX-License-Identifier: MIT

"""Github oauth app implementation for github integration."""

from invenio_oauthclient.contrib.github import GitHubOAuthSettingsHelper

from invenio_github.oauth.handlers import account_setup_handler, disconnect_handler

request_token_params = {"scope": "read:user,user:email,admin:repo_hook,read:org"}

helper = GitHubOAuthSettingsHelper()
github_app = helper.remote_app
github_app["disconnect_handler"] = disconnect_handler
github_app["signup_handler"]["setup"] = account_setup_handler
github_app["params"]["request_token_params"] = request_token_params
