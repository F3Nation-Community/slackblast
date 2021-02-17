import logging
from decouple import config
from fastapi import FastAPI, Request
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp
import datetime
import json


def get_categories():
    with open('categories.json') as c:
        data = json.load(c)
        return data


def formatted_categories(filteredcats):
    opts = []
    for cat in filteredcats:
        x = {
            "text": {
                "type": "plain_text",
                "text": cat["name"]
            },
            "value": str(cat["id"])
        }
        opts.append(x)
    return opts


logging.basicConfig(level=logging.DEBUG)
categories = []

slack_app = AsyncApp(
    token=config('SLACK_BOT_TOKEN'),
    signing_secret=config('SLACK_SIGNING_SECRET')
)
app_handler = AsyncSlackRequestHandler(slack_app)

categories = get_categories()


@slack_app.middleware  # or app.use(log_request)
async def log_request(logger, body, next):
    logger.debug(body)
    return await next()


@slack_app.event("app_mention")
async def event_test(body, say, logger):
    logger.info(body)
    await say("What's up yo?")


@slack_app.event("message")
async def handle_message():
    pass


@slack_app.command("/slackblast")
async def command(ack, body, respond, client, logger):
    await ack()
    today = datetime.datetime.now()
    datestring = today.strftime("%Y-%m-%d")

    res = await client.views_open(
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
                    "block_id": "title",
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
                    "type": "section",
                    "block_id": "the_ao",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*The AO*"
                    },
                    "accessory": {
                        "type": "channels_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select the AO",
                            "emoji": True
                        },
                        "action_id": "channels_select-action"
                    }
                },
                {
                    "type": "input",
                    "block_id": "date",
                    "element": {
                        "type": "datepicker",
                        "initial_date": datestring,
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
                    "block_id": "the_q",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*The Q*"
                    },
                    "accessory": {
                        "type": "users_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Tag the Q",
                            "emoji": True
                        },
                        "action_id": "users_select-action"
                    }
                },
                {
                    "type": "input",
                    "block_id": "the_pax",
                    "element": {
                        "type": "multi_users_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Tag the PAX",
                            "emoji": True
                        },
                        "action_id": "multi_users_select-action"
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "The PAX",
                        "emoji": True
                    }
                },
                {
                    "type": "input",
                    "block_id": "fngs",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "fng-action",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "List new FNG names separated by commas"
                        }
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "FNGs"
                    }
                },
                {
                    "type": "input",
                    "block_id": "count",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "count-action",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Total PAX count including FNGs"
                        }
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Count"
                    }
                },
                {
                    "type": "input",
                    "block_id": "moleskine",
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "action_id": "plain_text_input-action",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Tell us what happened"
                        }
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "The Moleskine",
                        "emoji": True
                    }
                }
            ]
        },
    )
    logger.info(res)


@slack_app.view("backblast-id")
async def view_submission(ack, body, logger, client):
    await ack()
    result = body["view"]["state"]["values"]
    title = result["title"]["title"]["value"]
    date = result["date"]["datepicker-action"]["selected_date"]
    the_ao = result["the_ao"]["channels_select-action"]["selected_channel"]
    the_q = result["the_q"]["users_select-action"]["selected_user"]
    pax = result["the_pax"]["multi_users_select-action"]["selected_users"]
    fngs = result["fngs"]["fng-action"]["value"]
    count = result["count"]["count-action"]["value"]
    moleskine = result["moleskine"]["plain_text_input-action"]["value"]

    pax_formatted = await get_pax(pax)

    logger.info(result)
    user = body["user"]["id"]
    chan = user
    if config('CHANNEL') != 'USER':
        chan = config('CHANNEL')

    msg = ""
    try:
        # formatting a message
        # todo: change to use json object
        msg = f"*Slackblast*: " + \
            "\n*Title*: " + title + \
            "\n*Date*: " + date + \
            "\n*AO*: <#" + the_ao + ">" + \
            "\n*Q*: <@" + the_q + ">" + \
            "\n*PAX*: " + pax_formatted + \
            "\n*FNGs*: " + fngs + \
            "\n*Count*: " + count + \
            "\n*Moleskine*:\n" + moleskine
    except Exception as e:
        # Handle error
        msg = "There was an error with your submission: " + e
    finally:
        # Message the user via the app/bot name
        if config('POST_TO_CHANNEL', cast=bool):
            await client.chat_postMessage(channel=chan, text=msg)


@slack_app.options("es_categories")
async def show_categories(ack, body, logger):
    await ack()
    lookup = body["value"]
    filtered = [x for x in categories if lookup.lower() in x["name"].lower()]
    output = formatted_categories(filtered)
    options = output
    logger.info(options)

    await ack(options=options)


async def get_pax(pax):
    p = ""
    for x in pax:
        p += "<@" + x + "> "
    return p


app = FastAPI()


@app.post("/slack/events")
async def endpoint(req: Request):
    return await app_handler.handle(req)


@app.get("/")
async def status_ok():
    return "ok"
