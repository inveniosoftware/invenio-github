..
    This file is part of Invenio.
    Copyright (C) 2016 CERN.

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


Usage
=====

Invenio-VCS allows you to flexibly configure multiple VCS providers and allow users to sync their repositories.
These can then be published as records (in InvenioRDM) or any other customisable action can be performed when a release is made.

Currently, the following VCS providers are officially supported in this module:

* GitHub
* GitLab

However, you can add support for any other provider (including non-Git ones) by implementing an abstract class.

This guide explains how to configure this module in general, while the corresponding guides for each provider go into more detail about the specific steps required.

===========
Quick start
===========

1. Choose which provider you'd like to use. We'll use GitHub in this example. In ``invenio.cfg`` create the provider factory corresponding to your provider:

  .. code-block:: python

    _vcs_github = GitHubProviderFactory(
        base_url="https://github.com",
        webhook_receiver_url="https://example.com/api/hooks/receivers/github/events/?access_token={token}",
    )

  These are the only two required arguments, and they're the same for all providers. For more details, see :ref:`provider-arguments`.


2. Configure the OAuth client. Each provider provides its own configuration for ``invenio-oauthclient`` through which users can authenticate to get the necessary access token for syncing their repositories.
   This should be added to any OAuth clients you may already have configured:

  .. code-block:: python

    OAUTHCLIENT_REMOTE_APPS = {
        "github": _vcs_github.remote_config,
    }

    OAUTHCLIENT_REST_REMOTE_APPS = {
        "github": _vcs_github.remote_config,
    }

  If you used a custom ``id`` when constructing the provider factory, this ID must correspond to that. The default ID for the GitHub provider is ``github``.

3. Register an OAuth application with the provider. For GitHub, this can be done through the `Developer Settings <https://github.com/settings/applications/new>`_. Please refer to the provider documentation for more details.

  Usually, you'll be asked for a redirect URL. By default, this will be of the form:

  .. code-block::

    https://example.com/oauth/authorized/github/

  where ``github`` corresponds to the ID of your provider factory.

  Once your app is registered, you'll be given a Client ID and Secret. You need to specify these to ``invenio-oauthclient``:

  .. code-block:: python

    GITHUB_APP_CREDENTIALS = {
        "consumer_key": "your_client_id",
        "consumer_secret": "your_client_secret",
    }

  .. note::

    The name of this config variable is specified by the ``credentials_key`` constructor argument of the provider factory. The '``GITHUB_``' is *not* derived from the ID, so you'll need to manually override this argument if you're using multiple instances of the same provider.

4. Register the provider. By adding provider factories to this list, you can enable each of them as a repository syncing method.

  .. code-block:: python

    VCS_PROVIDERS = [_vcs_github]

  You can add multiple of the same type of provider here. For example, you could have both public GitHub.com and a self-hosted GitHub Enterprise instance. The only requirement is to use a different ID and ``credentials_key`` for each provider factory.

  .. caution::

    Once repositories have been enabled from a given provider, removing it from this list is a dangerous operation. It's an unsupported behaviour that could cause unexpected errors and inconsistencies.

.. _provider-arguments:

==================
Provider arguments
==================

When constructing the provider factory, there are some common arguments that can be configured:

* ``base_url`` (**required**): the URL of the VCS instance, for example ``https://github.com``. This can correspond to either the public officially hosted instance or a self-hosted one.

* ``webhook_receiver_url`` (**required**): the endpoint on your Invenio server that will handle webhook events from GitHub.  This will almost always follow the pattern shown below, but can be customised depending on your use of ``invenio-webhooks``. The ``{token}`` variable can be placed anywhere in the URL and is used to validate the authenticity of the webhook call.

  .. code-block::

    https://example.com/api/hooks/receivers/github/events/?access_token={token}

* ``id``: uniquely identifies the provider within your instance. This value is used across database models and URLs to relate data to the provider. Once it has been used, the ID must not be changed. Each provider comes with a default ID (e.g. ``github``) but this should be changed if multiple instances of the same provider are being used.

* ``name``: the displayed name of the provider, e.g. ``GitHub``. You can, for example, set this to an institution-specific name to make it clear to users that it's not referring to the public instance.

* ``description``: a short text explaining the role of the provider in the instance. Shown in the user's OAuth settings page.

* ``credentials_key``: the name of the config variable specifying the OAuth Client ID and Secret for ``invenio-oauthclient``.

* ``config``: a dictionary of custom provider-specific configuration options.

=============
Configuration
=============

.. automodule:: invenio_vcs.config
   :members:
   :exclude-members: get_provider_by_id, get_provider_list
