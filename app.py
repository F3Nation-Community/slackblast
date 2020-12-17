# Import the async app instead of the regular one
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request
from slack_bolt import App
import logging
from decouple import config

logging.basicConfig(level=logging.DEBUG)


slack_app = App(
    token=config('SLACK_BOT_TOKEN'),
    signing_secret=config('SLACK_SIGNING_SECRET')
)


@slack_app.middleware  # or app.use(log_request)
def log_request(logger, body, next):
    logger.debug(body)
    return next()


@slack_app.event("app_mention")
def event_test(body, say, logger):
    logger.info(body)
    say("What's up yo?")


@slack_app.command("/backblast")
def command(ack, body, respond, client, logger):
    ack()
    res = client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "backblast-id",
            "title": {
                "type": "plain_text",
                "text": "Create a Backblast"
            },
            "submit": {
                "type": "plain_text",
                "text": "Submit"
            },
            "blocks": [
                {
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "title",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Snarky Title?"
                        }
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Title"
                    }
                },
                {
                    "type": "input",
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Choose an AO",
                            "emoji": True
                        },
                        "options": [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "*this is plain_text text*",
                                    "emoji": True
                                },
                                "value": "value-0"
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "*this is plain_text text*",
                                    "emoji": True
                                },
                                "value": "value-1"
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "*this is plain_text text*",
                                    "emoji": True
                                },
                                "value": "value-2"
                            }
                        ],
                        "action_id": "static_select-action"
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Workout",
                        "emoji": True
                    }
                },
                {
                    "type": "input",
                    "element": {
                        "type": "datepicker",
                        "initial_date": "1990-04-28",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a date",
                            "emoji": True
                        },
                        "action_id": "datepicker-action"
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Workout Date",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*The Q*"
                    },
                    "accessory": {
                        "type": "users_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a PAX",
                            "emoji": True
                        },
                        "action_id": "users_select-action"
                    }
                },
                {
                    "type": "input",
                    "element": {
                        "type": "multi_users_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select users",
                            "emoji": True
                        },
                        "action_id": "multi_users_select-action"
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "The Pax",
                        "emoji": True
                    }
                },
                {
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "action_id": "plain_text_input-action"
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "The Details",
                        "emoji": True
                    }
                }
            ]
        },
    )
    logger.info(res)


@slack_app.view("backblast-id")
def view_submission(ack, body, logger, client):
    ack()
    logger.info(body["view"]["state"]["values"])
    user = body["user"]["id"]
    msg = ""
    try:
        # Save to DB
        msg = f"Your submission of blah was successful"
    except Exception as e:
        # Handle error
        msg = "There was an error with your submission"
    finally:
        # Message the user
        client.chat_postMessage(channel=user, text=msg)


@slack_app.event("message")
def handle_message():
    pass

# Initialize the Flask app


app = Flask(__name__)
handler = SlackRequestHandler(slack_app)

# Register routes to Flask app


@app.route("/")
def hellow_world():
    return "ok"


@app.route("/slack/events", methods=["POST"])
def slack_events():
    # handler runs App's dispatch method
    response = handler.handle(request)
    return response
