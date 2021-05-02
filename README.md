# slackblast

Python web application needed to utilize modal window inside slack to make posting backblasts easier for PAX.

# environment variables

slackblast requires the following environment variables:

```
SLACK_BOT_TOKEN=<YOURTOKEN>
SLACK_VERIFICATION_TOKEN=<SLACKVERIFICATIONTOKEN>
SLACK_SIGNING_SECRET=<SLACKSIGNINGSECRET>
POST_TO_CHANNEL=<False or True>
CHANNEL=<USER or THE_AO or channel-id>
```

set `SLACK_BOT_TOKEN` from the token on the oath page in the slack app

set `SLACK_VERIFICATION_TOKEN` from the Basic Information -> Verification Token field in the settings for your slack app.

set `POST_TO_CHANNEL` equal to `True` or `False`. Set to true if you are using paxminer. Indicates whether or not to take the modal data and post to a channel in slack.

set `CHANNEL=channel-id` to the channel id (ID such as C01DB7S04KH -> NOT THE NAME) you want the modal results to post to by default.
set `CHANNEL=THE_AO` to post to the channel that was selected in the modal by default.
set `CHANNEL=USER` to post a DM from the slackblast to you with the results (testing) by default.
NOTE: In the modal, the user can choose where to post to.

See .env-f3nation-community file for help on local development

# slack app configuration

The url for your deployed app needs to be placed in three locations:

1. Interactivity and Shortcuts
   - Request URL
   - Options Load URL
2. Slash Commands
   - Request URL

**Format of the URL to be used**

```
https://<YOUR APP URL>/slack/events
```

**Scopes**

```
app_mentions:read
channels:read
chat:write
chat:write.public
commands
im:write
users:read
users:read.email
```

# deployment

main_slackblast contains the code to deploy on Azure via github repository. However, this will be unique to your own installation.

# notes

Use vscode locally with a `.env` file with the above variables. With vscode Azure extension you can right-click on 'Application Settings' and it will upload your `.env` variables right into the AppService.

Pushing to the github repo should trigger a new deployment to Azure if you set up the AppService correct.

# startup command(s)

To run locally:

```
pip install -r requirements.txt
gunicorn -k uvicorn.workers.UvicornWorker --bind "0.0.0.0:8000" --log-level debug app:app
```

See .env-f3nation-community file for help on local development
