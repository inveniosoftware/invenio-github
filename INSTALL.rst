Installation
============

Install the package into the same environment as your Invenio instance:

.. code-block:: console

   pip install invenio-github


In order to use it, you need to create a GitHub OAuth App. Follow the instructions
`here <https://docs.github.com/en/developers/apps/building-oauth-apps/creating-an-oauth-app>`_.
During the creation, note down the `client ID` and generate a `client secret`.

Now you need to create a random string to be used as `webhook secret`. You can use the following command to generate a random string:

.. code-block:: console

   openssl rand -hex 32

Then, you need to set the following variables in your Invenio configuration (`invenio.cfg`) in order to enable the GitHub OAuth client:


.. code-block:: python

   # Invenio-OAuthclient
   # -------------------
   
   OAUTHCLIENT_REMOTE_APPS = {
       "github": github_remote_app,
   }

   OAUTHCLIENT_REST_REMOTE_APPS = {
       "github": github_remote_app,
   }

   GITHUB_APP_CREDENTIALS = dict(
       consumer_key=<your_client_id>,
       consumer_secret=<your_client_secret>,
   )

    # Invenio-GitHub
    # ==============
    GITHUB_INTEGRATION_ENABLED = True
    GITHUB_WEBHOOK_RECEIVER_ID = "github"
    GITHUB_WEBHOOK_RECEIVER_URL = SITE_API_URL + "/receivers/github/events/?access_token={token}"
    GITHUB_SHARED_SECRET = <your_webhook_secret>

Make sure to replace `<your_client_id>`, `<your_client_secret>`, and `<your_webhook_secret>` with the actual values.

Local Test Instance
-------------------

If you are running a local test instance, you can use smee.io to forward GitHub webhooks to your local
instance. You can set it up as follows:

1. Go to <https://smee.io/> and create a new channel.
2. Set the `GITHUB_WEBHOOK_RECEIVER_URL` to the smee.io channel URL.

   .. code-block:: python

      GITHUB_WEBHOOK_RECEIVER_URL = "https://smee.io/<your_channel_id>/?access_token={token}"
   
3. Install the smee client:

   .. code-block:: console

      npm install -g smee-client

4. Run the smee client to forward the webhooks to your local instance:

   .. code-block:: console

      npx smee-client --url https://smee.io/<your_channel_id> --port 5000 --path /api/receivers/github/events/