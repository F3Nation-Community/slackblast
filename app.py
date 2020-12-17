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
def command(ack, body, respond, logger):
    ack()
    logger.info(body)
    respond(f"Hello <@{body['user_id']}>!")


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
