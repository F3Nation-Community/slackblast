# Slackblast

<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->

[![All Contributors](https://img.shields.io/badge/all_contributors-4-orange.svg?style=flat-square)](#contributors-)

<!-- ALL-CONTRIBUTORS-BADGE:END -->

Slackblast is a simple application you can get up and running in your Slack environment that will pop up a simple Backblast form for someone to fill out in the Slack App (mobile or desktop or web) when they type /slackblast. The advantage of slackblast is that it puts the backblast in a format that is compatible with [PAXminer](https://github.com/F3Nation-Community/PAXminer), which makes it easier to compile stats on users each month.

When the user types the /slackblast command and hits send, a window like the one below will pop up:

![Screenshot](https://raw.githubusercontent.com/F3Nation-Community/slackblast/main/SlackBlast%20Modal.png)

For a short tutorial on how to use the app, go to https://www.loom.com/share/705b67bfd30f40ae902fae7a6c1a7421

# Getting started

From a technical perspective, Slackblast is a Python web application that utilizes the modal window inside slack to make posting backblasts easier for PAX.

Go to https://api.slack.com/start/overview#creating to read up on how to create a slack app. Click their `Create a Slack app` while signed into your F3 region's Slack. The main idea is that you will set up a slashcommand, e.g. `/slackblast` or `/backblast`, that will send the request to your server that is running this web application (we recommend using a free Azure App Service) that will respond with a command to tell Slack to open up a modal with the fields to fill out a backblast post. When the user hits submit on the modal, the information will be sent to your server where it will then format it and post to the designated Slack channel!

Bonus: the post will be in a format friendly for Paxminer to mine and gather stats.

Bonus 2: the post can be emailed to automatically post to Wordpress

Go to https://azure.microsoft.com/en-us/services/app-service/ to create a Free Azure App Service to host this web application. The [VSCode Azure Extensions](https://code.visualstudio.com/docs/azure/extensions) will be helpful to upload your own .env file with your region's specific Slack and opinionated settings. See how to [integrate your Azure App Service with Github](https://github.com/MicrosoftDocs/azure-docs/blob/master/articles/app-service/deploy-continuous-deployment.md) for easy deployments.

When you finish setting up and installing the slackblast app in Slack, you will get a bot token also available under the OAuth & Permissions settings. You'll also get a verification token and signing secret on the Basic Information settings. You will plug that information into your own .env file. When you finish creating the Azure app, you will need to get the URL and add it (with `/slack/events` added to it) into three locations within the slackblast app settings. Lastly, you will need to add several Scopes to the Bot Token Scopes on the OAuth & Permissions settings. Read on for the nitty gritty details.

# All environment variables
The azure application requires a startup command to be added.  
Add 
```
gunicorn --config gunicorn.conf.py app:app
``` 
to `Settings -> Configuration -> General Settings -> Startup Command` in your Azure Portal 

https://docs.microsoft.com/en-us/azure/developer/python/media/deploy-azure/enter-startup-file-for-app-service-in-the-azure-portal.png


slackblast requires the following environment variables:

| Variable                     | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SLACK_BOT_TOKEN              | A value from the token on the OAuth page in the slack app                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| SLACK_VERIFICATION_TOKEN     | A value from the Basic Information -> Verification Token field in the settings for your slack app.                                                                                                                                                                                                                                                                                                                                                                                          |
| SLACK_SIGNING_SECRET         | Secret from the App Credentials page for your app in Slack.                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| POST_TO_CHANNEL              | A boolean value `True` or `False` that indicates whether or not to take the modal data and post to a channel in slack                                                                                                                                                                                                                                                                                                                                                                       |
| CHANNEL                      | The channel id (such as C01DB7S04KH -> NOT THE NAME) you want the modal results to post to by default. other values supported. set to `THE_AO` to post to the channel that was selected in the modal by default. Set to `USER` to post a DM from the slackblast to you with the results (testing) by default. If blank or missing, then the default channel will be the channel the user typed the slash command. In the modal, the user can choose the "destination" and where to post to. |
| EMAIL_SERVER                 | SMTP Server to use to send the email, default is `smtp.gmail.com` so if sending from a gmail account you only need to fill out email_user and email_password email                                                                                                                                                                                                                                                                                                                          |
| EMAIL_SERVER_PORT            | Email server port. default is `465`                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| EMAIL_USER                   | Email account to send on behalf of                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| EMAIL_PASSWORD               | Email account password                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| EMAIL_TO                     | To send the post to an email address. This will default the choice in the modal but can be changed by user. set `EMAIL_OPTION_HIDDEN_IN_MODAL` to prevent user from changing it.                                                                                                                                                                                                                                                                                                            |
| EMAIL_OPTION_HIDDEN_IN_MODAL | Hide the option from the PAX on sending an email in the modal                                                                                                                                                                                                                                                                                                                                                                                                                               |

<br><br>

# Slack App Configuration

The url for your deployed app needs to be placed in three locations in the slackblast app in Slack:

1. Interactivity and Shortcuts
   - Request URL
   - Options Load URL
2. Slash Commands
   - Request URL

**Format of the URL to be used**

```
https://<YOUR-APP-URL>/slack/events
```

**Scopes**  
Under `OAuth & Permissions` you need to add the following scopes
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

<br>

# Email

All of the email user and password variables will need to be set in order to send an email with the modal contents to the address specified.

## Create Posts by email

Wordpress allows you to send a post to a special address via email and it will convert it to a post.

If you are using hosted wordpress set the `EMAIL_TO` address to the random Wordpress email generated by Wordpress, [more information](<https://wordpress.com/support/post-by-email/#:~:text=Go%20to%20My%20Site(s,posts%20by%20sending%20an%20email%E2%80%9D)>).

If you are not using hosted wordpress, then you can create a dedicated gmail or other account and use this address.

See .env-f3nation-community file for help on local development.
<br><br>

# Deployment

Go to Azure App Services > Deployment Center and set up an integration with your Github repo where you forked this repo and have the Slackblast code. Azure will create a main\_<your-azure-appname>.yml file under .github/workflows folder, but it should be hidden by default and you should not need to worry about it. Whenever you make any change to your `main` branch, it will deploy the most recent code.

Here is further reading if you want to know what is going on under the hood.

- Docs for the Azure Web Apps Deploy action: https://github.com/Azure/webapps-deploy
- More GitHub Actions for Azure: https://github.com/Azure/actions
- More info on Python, GitHub Actions, and Azure App Service: https://aka.ms/python-webapps-actions

# Notes

Use vscode locally with a `.env` file with the above variables. With vscode Azure extension, you can right-click on 'Application Settings' and it will upload your `.env` variables right into the AppService.

Pushing to the github repo should trigger a new deployment to Azure if you set up the AppService correct.
<br><br>

# Startup command(s)

To run locally:

## python
```
pip install -r requirements.txt
gunicorn -k uvicorn.workers.UvicornWorker --bind "0.0.0.0:8000" --log-level debug app:app
```

In another console, use the url output by ngrok to update your slackblast app settings:

```
ngrok http 8000
```
See .env-f3nation-community file for more details on local development
<br><br>

## docker
If you have docker installed you can build and run locally by taking advantage of containerization.  The built image could potentially be deployed and started remotely as well.

You can build a local docker container by executing 
```
docker build -t slackblast:latest .
``` 
 
Once you have built and installed the docker container locally you can run the following command to start the container.

```
docker run -d -p 8000:8000 --env-file /path/to/your/.env --name slackblast --restart unless-stopped slackblast:latest
```

# Contributors ✨

Thanks goes to these awesome PAX ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tr>
    <td align="center"><a href="https://github.com/wolfpackt99"><img src="https://avatars.githubusercontent.com/u/2165251?v=4?s=100" width="100px;" alt=""/><br /><sub><b>Trent</b></sub></a><br /><a href="#ideas-wolfpackt99" title="Ideas, Planning, & Feedback">🤔</a> <a href="https://github.com/F3Nation-Community/slackblast/commits?author=wolfpackt99" title="Code">💻</a> <a href="https://github.com/F3Nation-Community/slackblast/commits?author=wolfpackt99" title="Documentation">📖</a> <a href="#mentoring-wolfpackt99" title="Mentoring">🧑‍🏫</a> <a href="https://github.com/F3Nation-Community/slackblast/pulls?q=is%3Apr+reviewed-by%3Awolfpackt99" title="Reviewed Pull Requests">👀</a></td>
    <td align="center"><a href="https://github.com/yankeestom"><img src="https://avatars.githubusercontent.com/u/34582097?v=4?s=100" width="100px;" alt=""/><br /><sub><b>yankeestom</b></sub></a><br /><a href="#ideas-yankeestom" title="Ideas, Planning, & Feedback">🤔</a> <a href="https://github.com/F3Nation-Community/slackblast/commits?author=yankeestom" title="Code">💻</a> <a href="https://github.com/F3Nation-Community/slackblast/pulls?q=is%3Apr+reviewed-by%3Ayankeestom" title="Reviewed Pull Requests">👀</a></td>
    <td align="center"><a href="https://github.com/willhlaw"><img src="https://avatars.githubusercontent.com/u/943510?v=4?s=100" width="100px;" alt=""/><br /><sub><b>willhlaw</b></sub></a><br /><a href="#ideas-willhlaw" title="Ideas, Planning, & Feedback">🤔</a> <a href="https://github.com/F3Nation-Community/slackblast/commits?author=willhlaw" title="Code">💻</a> <a href="https://github.com/F3Nation-Community/slackblast/commits?author=willhlaw" title="Documentation">📖</a> <a href="#projectManagement-willhlaw" title="Project Management">📆</a></td>
    <td align="center"><a href="https://github.com/jim-muzzall"><img src="https://avatars.githubusercontent.com/u/88450074?v=4?s=100" width="100px;" alt=""/><br /><sub><b>jim-muzzall</b></sub></a><br /><a href="#ideas-jim-muzzall" title="Ideas, Planning, & Feedback">🤔</a> <a href="https://github.com/F3Nation-Community/slackblast/commits?author=jim-muzzall" title="Documentation">📖</a></td>
  </tr>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!
