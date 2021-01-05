# slackblast

Python web application needed to utilize modal window inside slack to make posting backblasts easier for PAX.

# environment variables

slackblast requires the following environment variables:

```
SLACK_BOT_TOKEN=<YOURTOKEN>
SLACK_VERIFICATION_TOKEN=<SLACKVERIFICATIONTOKEN>
SLACK_SIGNING_SECRET=<SLACKSIGNINGSECRET>
PORT=<PORT>
POST_TO_CHANNEL=<False or True>
CHANNEL=USER
```

set `SLACK_BOT_TOKEN` from the token on the oath page in the slack app

set `SLACK_VERIFICATION_TOKEN` from the Basic Information -> Verification Token field in the settings for your slack app.

set `PORT` equal to the port used below in the startup command

set `POST_TO_CHANNEL` equal to `True` or `False`. Set to true if you are using paxminer. Indicates whether or not to take the modal data and post to a channel in slack.

set `CHANNEL` equal to the channel id you wan the modal results to post in otherwise use `USER` to post a DM from the slackblast to you with the results (testing).

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

# startup command

```
gunicorn -k uvicorn.workers.UvicornWorker --bind "0.0.0.0:8000" --log-level debug app:app
```
