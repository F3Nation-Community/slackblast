import logging
from decouple import config, UndefinedValueError
from fastapi import FastAPI, Request
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp
import datetime
from datetime import datetime, timezone, timedelta
import json

import sendmail


# def get_categories():
#     with open('categories.json') as c:
#         data = json.load(c)
#         return data


# def formatted_categories(filteredcats):
#     opts = []
#     for cat in filteredcats:
#         x = {
#             "text": {
#                 "type": "plain_text",
#                 "text": cat["name"]
#             },
#             "value": str(cat["id"])
#         }
#         opts.append(x)
#     return opts

OPTIONAL_INPUT_VALUE = "None"


logging.basicConfig(level=logging.DEBUG)
#categories = []

slack_app = AsyncApp(
    token=config('SLACK_BOT_TOKEN'),
    signing_secret=config('SLACK_SIGNING_SECRET')
)
app_handler = AsyncSlackRequestHandler(slack_app)

#categories = get_categories()


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


def safeget(dct, *keys):
    for key in keys:
        try:
            dct = dct[key]
        except KeyError:
            return None
    return dct


def get_channel_id_and_name(body, logger):
    # returns channel_iid, channel_name if it exists as an escaped parameter of slashcommand
    user_id = body.get("user_id")
    # Get "text" value which is everything after the /slash-command
    # e.g. /slackblast #our-aggregate-backblast-channel
    # then text would be "#our-aggregate-backblast-channel" if /slash command is not encoding
    # but encoding needs to be checked so it will be "<#C01V75UFE56|our-aggregate-backblast-channel>" instead
    channel_name = body.get("text") or ''
    channel_id = ''
    try:
        channel_id = channel_name.split('|')[0].split('#')[1]
        channel_name = channel_name.split('|')[1].split('>')[0]
    except IndexError as ierr:
        logger.error('Bad user input - cannot parse channel id')
    except Exception as error:
        logger.error('User did not pass in any input')
    return channel_id, channel_name


async def get_channel_name(id, logger, client):
    channel_info_dict = await client.conversations_info(
        channel=id
    )
    channel_name = safeget(channel_info_dict, 'channel', 'name') or None
    logger.info('channel_name is {}'.format(channel_name))
    return channel_name


async def get_user_names(array_of_user_ids, logger, client):
    names = []
    for user_id in array_of_user_ids:
        user_info_dict = await client.users_info(
            user=user_id
        )
        user_name = safeget(user_info_dict, 'user', 'profile', 'display_name') or safeget(
            user_info_dict, 'user', 'profile', 'real_name') or None
        if user_name:
            names.append(user_name)
        logger.info('user_name is {}'.format(user_name))
    logger.info('names are {}'.format(names))
    return names


@slack_app.command("/slackblast")
@slack_app.command("/backblast")
async def command(ack, body, respond, client, logger):
    await ack()
    today = datetime.now(timezone.utc).astimezone()
    today = today - timedelta(hours=6)
    datestring = today.strftime("%Y-%m-%d")
    user_id = body.get("user_id")

    # Figure out where user sent slashcommand from to set current channel id and name
    is_direct_message = body.get("channel_name") == 'directmessage'
    current_channel_id = user_id if is_direct_message else body.get(
        "channel_id")
    current_channel_name = "Me" if is_direct_message else body.get(
        "channel_id")

    # The channel where user submitted the slashcommand
    current_channel_option = {
        "text": {
            "type": "plain_text",
            "text": "Current Channel"
        },
        "value": current_channel_id
    }

    # In .env, CHANNEL=USER
    channel_me_option = {
        "text": {
            "type": "plain_text",
            "text": "Me"
        },
        "value": user_id
    }
    # In .env, CHANNEL=THE_AO
    channel_the_ao_option = {
        "text": {
            "type": "plain_text",
            "text": "The AO Channel"
        },
        "value": "THE_AO"
    }
    # In .env, CHANNEL=<channel-id>
    channel_configured_ao_option = {
        "text": {
            "type": "plain_text",
            "text": "Preconfigured Backblast Channel"
        },
        "value": config('CHANNEL', default=current_channel_id)
    }
    # User may have typed /slackblast #<channel-name> AND
    # slackblast slashcommand is checked to escape channels.
    #   Escape channels, users, and links sent to your app
    #   Escaped: <#C1234|general>
    channel_id, channel_name = get_channel_id_and_name(body, logger)
    channel_user_specified_channel_option = {
        "text": {
            "type": "plain_text",
            "text": '# ' + channel_name
        },
        "value": channel_id
    }

    channel_options = []

    # figure out which channel should be default/initial and then remaining operations
    if channel_id:
        initial_channel_option = channel_user_specified_channel_option
        channel_options.append(channel_user_specified_channel_option)
        channel_options.append(current_channel_option)
        channel_options.append(channel_me_option)
        channel_options.append(channel_the_ao_option)
        channel_options.append(channel_configured_ao_option)
    elif config('CHANNEL', default=current_channel_id) == 'USER':
        initial_channel_option = channel_me_option
        channel_options.append(channel_me_option)
        channel_options.append(current_channel_option)
        channel_options.append(channel_the_ao_option)
    elif config('CHANNEL', default=current_channel_id) == 'THE_AO':
        initial_channel_option = channel_the_ao_option
        channel_options.append(channel_the_ao_option)
        channel_options.append(current_channel_option)
        channel_options.append(channel_me_option)
    elif config('CHANNEL', default=current_channel_id) == current_channel_id:
        # if there is no .env CHANNEL value, use default of current channel
        initial_channel_option = current_channel_option
        channel_options.append(current_channel_option)
        channel_options.append(channel_me_option)
        channel_options.append(channel_the_ao_option)
    else:
        # Default to using the .env CHANNEL value which at this point must be a channel id
        initial_channel_option = channel_configured_ao_option
        channel_options.append(channel_configured_ao_option)
        channel_options.append(current_channel_option)
        channel_options.append(channel_me_option)
        channel_options.append(channel_the_ao_option)

    blocks = [
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
            "type": "input",
            "block_id": "the_ao",
            "element": {
                "type": "channels_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select the AO",
                    "emoji": True
                },
                "action_id": "channels_select-action"
            },
            "label": {
                "type": "plain_text",
                "text": "The AO",
                "emoji": True
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
            "type": "input",
            "block_id": "the_q",
            "element": {
                "type": "users_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Tag the Q",
                    "emoji": True
                },
                "action_id": "users_select-action"
            },
            "label": {
                "type": "plain_text",
                "text": "The Q",
                "emoji": True
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
                "initial_value": "None",
                "placeholder": {
                    "type": "plain_text",
                    "text": "FNGs"
                }
            },
            "label": {
                "type": "plain_text",
                "text": "List untaggable names separated by commas (FNGs, Willy Lomans, etc.)"
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
                "initial_value": "WARMUP: \nTHE THANG: \nMARY: \nANNOUNCEMENTS: \nCOT: ",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Tell us what happened\n\n"
                }
            },
            "label": {
                "type": "plain_text",
                "text": "The Moleskine",
                "emoji": True
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "block_id": "destination",
            "text": {
                "type": "plain_text",
                "text": "Choose where to post this"
            },
            "accessory": {
                "action_id": "destination-action",
                "type": "static_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Choose where"
                },
                "initial_option": initial_channel_option,
                "options": channel_options
            }
        }
    ]

    if config('EMAIL_TO', default='') and not config('EMAIL_OPTION_HIDDEN_IN_MODAL', default=False, cast=bool):
        blocks.append({
            "type": "input",
            "block_id": "email",
            "element": {
                "type": "plain_text_input",
                "action_id": "email-action",
                "initial_value": config('EMAIL_TO', default=OPTIONAL_INPUT_VALUE),
                "placeholder": {
                    "type": "plain_text",
                    "text": "Type an email address or {}".format(OPTIONAL_INPUT_VALUE)
                }
            },
            "label": {
                "type": "plain_text",
                "text": "Send Email"
            }
        })

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
            "blocks": blocks
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
    destination = result["destination"]["destination-action"]["selected_option"]["value"]
    email_to = safeget(result, "email", "email-action", "value")
    the_date = result["date"]["datepicker-action"]["selected_date"]

    pax_formatted = await get_pax(pax)

    logger.info(result)

    chan = destination
    if chan == 'THE_AO':
        chan = the_ao

    logger.info('Channel to post to will be {} because the selected destination value was {} while the selected AO in the modal was {}'.format(
        chan, destination, the_ao))

    ao_name = await get_channel_name(the_ao, logger, client)
    q_name = (await get_user_names([the_q], logger, client) or [''])[0]
    pax_names = ', '.join(await get_user_names(pax, logger, client) or [''])

    msg = ""
    try:
        # formatting a message
        # todo: change to use json object
        header_msg = f"*Slackblast*: "
        title_msg = f"*" + title + "*"

        date_msg = f"*DATE*: " + the_date
        ao_msg = f"*AO*: <#" + the_ao + ">"
        q_msg = f"*Q*: <@" + the_q + ">"
        pax_msg = f"*PAX*: " + pax_formatted
        fngs_msg = f"*FNGs*: " + fngs
        count_msg = f"*COUNT*: " + count
        moleskine_msg = moleskine

        # Message the user via the app/bot name
        if config('POST_TO_CHANNEL', cast=bool):
            body = make_body(date_msg, ao_msg, q_msg, pax_msg,
                             fngs_msg, count_msg, moleskine_msg)
            msg = header_msg + "\n" + title_msg + "\n" + body
            await client.chat_postMessage(channel=chan, text=msg)
            logger.info('\nMessage posted to Slack! \n{}'.format(msg))
    except Exception as slack_bolt_err:
        logger.error('Error with posting Slack message with chat_postMessage: {}'.format(
            slack_bolt_err))
        # Try again and bomb out without attempting to send email
        await client.chat_postMessage(channel=chan, text='There was an error with your submission: {}'.format(slack_bolt_err))
    try:
        if email_to and email_to != OPTIONAL_INPUT_VALUE:
            subject = title

            date_msg = f"DATE: " + the_date
            ao_msg = f"AO: " + (ao_name or '').replace('the', '').title()
            q_msg = f"Q: " + q_name
            pax_msg = f"PAX: " + pax_names
            fngs_msg = f"FNGs: " + fngs
            count_msg = f"COUNT: " + count
            moleskine_msg = moleskine

            body_email = make_body(
                date_msg, ao_msg, q_msg, pax_msg, fngs_msg, count_msg, moleskine_msg)
            sendmail.send(subject=subject, recipient=email_to, body=body_email)

            logger.info('\nEmail Sent! \n{}'.format(body_email))
    except UndefinedValueError as email_not_configured_error:
        logger.info('Skipping sending email since no EMAIL_USER or EMAIL_PWD found. {}'.format(
            email_not_configured_error))
    except Exception as sendmail_err:
        logger.error('Error with sendmail: {}'.format(sendmail_err))


def make_body(date, ao, q, pax, fngs, count, moleskine):
    return date + \
        "\n" + ao + \
        "\n" + q + \
        "\n" + pax + \
        "\n" + fngs + \
        "\n" + count + \
        "\n" + moleskine


# @slack_app.options("es_categories")
# async def show_categories(ack, body, logger):
#     await ack()
#     lookup = body["value"]
#     filtered = [x for x in categories if lookup.lower() in x["name"].lower()]
#     output = formatted_categories(filtered)
#     options = output
#     logger.info(options)

#     await ack(options=options)


async def get_pax(pax):
    p = ""
    for x in pax:
        p += "<@" + x + "> "
    return p


app = FastAPI()


@app.post("/slack/events")
async def endpoint(req: Request):
    logging.debug('[In app.post("/slack/events")]')
    return await app_handler.handle(req)


@app.get("/")
async def status_ok():
    logging.debug('[In app.get("/")]')
    return "ok"
