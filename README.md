# slackblast

Python web application needed to utilize modal window inside slack to make posting backblasts easier for PAX.

# environment variables

slackblast requires the following environment variables:

```
SLACK_BOT_TOKEN=<YOURTOKEN>
SLACK_VERIFICATION_TOKEN=<SLACKVERIFICATIONTOKEN>
SLACK_SIGNING_SECRET=<SLACKSIGNINGSECRET>
PORT=<PORT>
```

# deployment

main_slackblast contains the code to deploy on Azure via github repository

# notes

Use vscode locally with a `.env` file with the above variables. With vscode Azure extension you can right-click on 'Application Settings' and it will upload your `.env` variables right into the AppService.

Pushing to the github repo should trigger a new deployment to Azure if you set up the AppService correct.
