import logging
import json
import os
import datetime
from datetime import datetime, timezone, timedelta
import re
import pandas as pd

from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from slack_bolt.adapter.aws_lambda.lambda_s3_oauth_flow import LambdaS3OAuthFlow

import mysql.connector
from contextlib import ContextDecorator
# import sendmail


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

logger = logging.getLogger()
logger.setLevel(logging.INFO)
# logging.basicConfig(level=logging.DEBUG)
#categories = []

# process_before_response must be True when running on FaaS
slack_app = App(
    process_before_response=True,
    oauth_flow=LambdaS3OAuthFlow(),
)

#categories = get_categories()

# Construct class for connecting to the db
# Takes team_id as an input, pulls schema name from paxminer.regions
class my_connect(ContextDecorator):
    def __init__(self):
        self.conn = ''

    def __enter__(self):
        self.conn = mysql.connector.connect(
            host=os.environ['DATABASE_HOST'],
            user=os.environ['ADMIN_DATABASE_USER'],
            passwd=os.environ['ADMIN_DATABASE_PASSWORD'],
            database=os.environ['ADMIN_DATABASE_SCHEMA']
        )
        return self

    def __exit__(self, *exc):
        self.conn.close()
        return False


@slack_app.middleware  # or app.use(log_request)
def log_request(logger, body, next):
    logger.debug(body)
    return next()


@slack_app.event("app_mention")
def event_test(body, say, logger):
    logger.info(body)
    say("What's up yo?")


@slack_app.event("message")
def handle_message():
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


def get_channel_name(id, logger, client):
    channel_info_dict = client.conversations_info(
        channel=id
    )
    channel_name = safeget(channel_info_dict, 'channel', 'name') or None
    logger.info('channel_name is {}'.format(channel_name))
    return channel_name


def get_user_names(array_of_user_ids, logger, client, return_urls = False):
    names = []
    urls = []
    for user_id in array_of_user_ids:
        user_info_dict = client.users_info(
            user=user_id
        )
        user_name = safeget(user_info_dict, 'user', 'profile', 'display_name') or safeget(
            user_info_dict, 'user', 'profile', 'real_name') or None
        if user_name:
            names.append(user_name)
        logger.info('user_name is {}'.format(user_name))

        user_icon_url = user_info_dict['user']['profile']['image_192']
        urls.append(user_icon_url)
    logger.info('names are {}'.format(names))

    if return_urls:
        return names, urls
    else:
        return names

def get_user_ids(user_names, client):
    member_list = pd.DataFrame(client.users_list()['members'])
    member_list = member_list.drop('profile', axis=1).join(pd.DataFrame(member_list.profile.values.tolist()), rsuffix='_profile')
    member_list['display_name2'] = member_list['display_name']
    member_list.loc[(member_list['display_name']==''), ('display_name2')] = member_list['real_name']
    member_list['display_name2'] = member_list['display_name2'].str.lower()
    member_list['display_name2'].replace('\s\(([\s\S]*?\))','',regex=True, inplace=True)
    
    user_ids = []
    for user_name in user_names:
        user_name = user_name.replace('_', ' ').lower()
        try:
            user = f"<@{member_list.loc[(member_list['display_name2']==user_name), ('id')].iloc[0]}>"
            print(f'Found {user_name}: {user}')
        except:
            user = user_name
        user_ids.append(user)
    
    return user_ids

def parse_moleskin_users(msg, client):
    pattern = "@([A-Za-z0-9-']+)"
    user_ids = get_user_ids(re.findall(pattern, msg), client)

    msg2 = re.sub(pattern, '{}', msg).format(*user_ids)
    return msg2

def respond_to_slack_within_3_seconds(body, ack):
    ack("Opening form...")

def command(ack, body, respond, client, logger):
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
        # "value": config('CHANNEL', default=current_channel_id)
        "value": current_channel_id
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
    # elif config('CHANNEL', default=current_channel_id) == 'USER':
    elif current_channel_id == 'USER':
        initial_channel_option = channel_me_option
        channel_options.append(channel_me_option)
        channel_options.append(current_channel_option)
        channel_options.append(channel_the_ao_option)
    # elif config('CHANNEL', default=current_channel_id) == 'THE_AO':
    elif current_channel_id == 'THE_AO':
        initial_channel_option = channel_the_ao_option
        channel_options.append(channel_the_ao_option)
        channel_options.append(current_channel_option)
        channel_options.append(channel_me_option)
    # elif config('CHANNEL', default=current_channel_id) == current_channel_id:
    elif current_channel_id == current_channel_id:
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

    # determine if backblast or preblast
    is_preblast = body.get("command") == '/preblast'

    if is_preblast:
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
                "block_id": "time",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "time-action",
                    "initial_value": "0530",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Workout time"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Workout Time"
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
            # {
            #     "type": "input",
            #     "block_id": "the_coq",
            #     "element": {
            #         "type": "users_select",
            #         "placeholder": {
            #             "type": "plain_text",
            #             "text": "Tag the CoQ(s)",
            #             "emoji": True
            #         },
            #         "action_id": "multi_users_select-action"
            #     },
            #     "label": {
            #         "type": "plain_text",
            #         "text": "The CoQs, if applicable",
            #         "emoji": True
            #     },
            #     "optional": True
            # },
            {
                "type": "input",
                "block_id": "why",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "why-action",
                    "initial_value": "None",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Explain the why"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "The Why"
                }
            },
            {
                "type": "input",
                "block_id": "coupon",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "coupon-action",
                    "initial_value": "None",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Coupons or not?"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Coupons"
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
                        "text": "Any message for FNGs?"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "FNGs"
                }
            },
            {
                "type": "input",
                "block_id": "moleskine",
                "element": {
                    "type": "plain_text_input",
                    "multiline": True,
                    "action_id": "plain_text_input-action",
                    "initial_value": "None",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Any additional beatdown detail, announcements, etc.\n\n"
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
                "type": "input",
                "block_id": "destination",
                "element": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select an item",
                        "emoji": True
                    },
                    "options": channel_options,
                    "initial_option": initial_channel_option,
                    "action_id": "destination-input"
                },
                "label": {
                    "type": "plain_text",
                    "text": "Choose where to post this",
                    "emoji": True
                }
            },
            {
            "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": "Please wait after hitting Submit!",
                        "emoji": True
                    }
                ]
            }
        ]
        view = {
            "type": "modal",
            "callback_id": "preblast-id",
            "title": {
                "type": "plain_text",
                "text": "Create a Preblast"
            },
            "submit": {
                "type": "plain_text",
                "text": "Submit"
            },
            "blocks": blocks
        }
    else:
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
                "block_id": "the_coq",
                "element": {
                    "type": "multi_users_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Tag the CoQ(s)",
                        "emoji": True
                    },
                    "action_id": "multi_users_select-action"
                },
                "label": {
                    "type": "plain_text",
                    "text": "The CoQ(s), if applicable",
                    "emoji": True
                },
                "optional": True
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": "Note, only the first CoQ is tracked by PAXMiner",
                        "emoji": True
                    }
                ]
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
                "block_id": "non_slack_pax",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "non_slack_pax-action",
                    "initial_value": "None",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Non-Slackers"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "List untaggable PAX separated by commas (not including FNGs)"
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
                    "text": "List FNGs separated by commas"
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
                    "initial_value": "\n*WARMUP:* \n*THE THANG:* \n*MARY:* \n*ANNOUNCEMENTS:* \n*COT:* ",
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
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": "If trying to tag PAX in here, substitute _ for spaces and do not include titles in parenthesis (ie, @Moneyball not @Moneyball_(F3_STC)). Spelling is important, capitalization is not!",
                        "emoji": True
                    }
                ]
            },
            {
                "type": "divider"
            },
            # {
            #     "type": "section",
            #     "block_id": "destination",
            #     "text": {
            #         "type": "plain_text",
            #         "text": "Choose where to post this"
            #     },
            #     "accessory": {
            #         "action_id": "destination-action",
            #         "type": "static_select",
            #         "placeholder": {
            #             "type": "plain_text",
            #             "text": "Choose where"
            #         },
            #         "initial_option": initial_channel_option,
            #         "options": channel_options
            #     }
            # },
            {
                "type": "input",
                "block_id": "destination",
                "element": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select an item",
                        "emoji": True
                    },
                    "options": channel_options,
                    "initial_option": initial_channel_option,
                    "action_id": "destination-input"
                },
                "label": {
                    "type": "plain_text",
                    "text": "Choose where to post this",
                    "emoji": True
                }
            },
            {
            "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": "Please wait after hitting Submit!",
                        "emoji": True
                    }
                ]
            }
        ]
        view = {
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
        }

    # if config('EMAIL_TO', default='') and not config('EMAIL_OPTION_HIDDEN_IN_MODAL', default=False, cast=bool):
    #     blocks.append({
    #         "type": "input",
    #         "block_id": "email",
    #         "element": {
    #             "type": "plain_text_input",
    #             "action_id": "email-action",
    #             "initial_value": config('EMAIL_TO', default=OPTIONAL_INPUT_VALUE),
    #             "placeholder": {
    #                 "type": "plain_text",
    #                 "text": "Type an email address or {}".format(OPTIONAL_INPUT_VALUE)
    #             }
    #         },
    #         "label": {
    #             "type": "plain_text",
    #             "text": "Send Email"
    #         }
    #     })

    res = client.views_open(
        trigger_id=body["trigger_id"],
        view=view,
    )
    logger.info(res)
        

def config_slackblast(body, client, context):
    team_id = context['team_id']
    bot_token = context['bot_token']
    
    blocks = [
		{
			"type": "input",
            "block_id": "email_enable",
			"element": {
				"type": "radio_buttons",
				"options": [
					{
						"text": {
							"type": "plain_text",
							"text": "Enable email",
							"emoji": True
						},
						"value": "enable"
					},
					{
						"text": {
							"type": "plain_text",
							"text": "Disable email",
							"emoji": True
						},
						"value": "disable"
					},                    
				],
				"action_id": "email_enable"
			},
			"label": {
				"type": "plain_text",
				"text": "Slackblast Email",
				"emoji": True
			}
		},
        {
            "type": "input",
            "block_id": "email_server",
            "element": {
                "type": "plain_text_input",
                "action_id": "email_server",
                "initial_value": "smtp.gmail.com"
            },
            "label": {
                "type": "plain_text",
                "text": "Email Server"
            }
        },
        {
            "type": "input",
            "block_id": "email_port",
            "element": {
                "type": "plain_text_input",
                "action_id": "email_port",
                "initial_value": "465"
            },
            "label": {
                "type": "plain_text",
                "text": "Email Server Port"
            }
        },
        {
            "type": "input",
            "block_id": "email_user",
            "element": {
                "type": "plain_text_input",
                "action_id": "email_user",
                "initial_value": "example_sender@gmail.com"
            },
            "label": {
                "type": "plain_text",
                "text": "Email From Address"
            }
        },
        {
            "type": "input",
            "block_id": "email_password",
            "element": {
                "type": "plain_text_input",
                "action_id": "email_password",
                "initial_value": "example_pwd_123"
            },
            "label": {
                "type": "plain_text",
                "text": "Email Password"
            }
        },
        {
            "type": "input",
            "block_id": "email_to",
            "element": {
                "type": "plain_text_input",
                "action_id": "email_to",
                "initial_value": "example_destination@gmail.com"
            },
            "label": {
                "type": "plain_text",
                "text": "Email To Address"
            }
        }
    ]
    view = {
        "type": "modal",
        "callback_id": "config-slackblast",
        "title": {
            "type": "plain_text",
            "text": "Configure settings"
        },
        "submit": {
            "type": "plain_text",
            "text": "Submit"
        },
        "blocks": blocks
    }

    res = client.views_open(
        trigger_id=body["trigger_id"],
        view=view,
    )
    logger.info(res)

@slack_app.view("config-slackblast")
def view_submission(ack, body, logger, client, context):
    ack()
    team_id = context['team_id']
    bot_token = context['bot_token']

    # gather inputs
    result = body["view"]["state"]["values"]
    email_enable = result['email_enable']['email_enable']['selected_option'] == "enable"
    email_server = result['email_server']['email_server']['value']
    email_port = result['email_port']['email_port']['value']
    email_user = result['email_user']['email_user']['value']
    email_password = result['email_password']['email_password']['value']
    email_to = result['email_to']['email_to']['value']

    # build SQL insert / update statement
    sql_insert = f"""
    INSERT INTO regions 
    SET team_id='{team_id}', bot_token='{bot_token}', email_enable={email_enable}, email_server='{email_server}', 
        email_server_port={email_port}, email_user='{email_user}', email_password='{email_password}', email_to='{email_to}'
    ON DUPLICATE KEY UPDATE
        team_id='{team_id}', bot_token='{bot_token}', email_enable={email_enable}, email_server='{email_server}', 
        email_server_port={email_port}, email_user='{email_user}', email_password='{email_password}', email_to='{email_to}'
    ;
    """

    # attempt update
    logging.info(f"Attempting SQL insert / update: {sql_insert}")
    try:
        with my_connect(team_id) as mydb:
            mycursor = mydb.conn.cursor()
            mycursor.execute(sql_insert)
            mycursor.execute("COMMIT;")
    except Exception as e:
        logging.error(f"Error writing to db: {e}")
        error_msg = e

slack_app.command("/config-slackblast")(
    ack=respond_to_slack_within_3_seconds,
    lazy=[config_slackblast]
)

slack_app.command("/slackblast")(
    ack=respond_to_slack_within_3_seconds,
    lazy=[command]
)

slack_app.command("/backblast")(
    ack=respond_to_slack_within_3_seconds,
    lazy=[command]
)

slack_app.command("/preblast")(
    ack=respond_to_slack_within_3_seconds,
    lazy=[command]
)


@slack_app.view("backblast-id")
def view_submission(ack, body, logger, client):
    ack()
    result = body["view"]["state"]["values"]
    title = result["title"]["title"]["value"]
    date = result["date"]["datepicker-action"]["selected_date"]
    the_ao = result["the_ao"]["channels_select-action"]["selected_channel"]
    the_q = result["the_q"]["users_select-action"]["selected_user"]
    the_coq = result["the_coq"]["multi_users_select-action"]["selected_users"]
    pax = result["the_pax"]["multi_users_select-action"]["selected_users"]
    non_slack_pax = result["non_slack_pax"]["non_slack_pax-action"]["value"]
    fngs = result["fngs"]["fng-action"]["value"]
    count = result["count"]["count-action"]["value"]
    moleskine = result["moleskine"]["plain_text_input-action"]["value"]
    destination = result["destination"]["destination-input"]["selected_option"]["value"]
    email_to = safeget(result, "email", "email-action", "value")
    the_date = result["date"]["datepicker-action"]["selected_date"]

    pax_formatted = get_pax(pax)
    pax_full_list = [pax_formatted]
    fngs_formatted = fngs
    if non_slack_pax != 'None':
        pax_full_list.append(non_slack_pax)
    if fngs != 'None':
        pax_full_list.append(fngs)
        fngs_formatted = str(fngs.count(',') + 1) + ' ' + fngs
    pax_formatted = ', '.join(pax_full_list)

    if the_coq == []:
        the_coqs_formatted = ''
    else:
        the_coqs_formatted = get_pax(the_coq)
        the_coqs_full_list = [the_coqs_formatted]
        the_coqs_formatted = ', ' + ', '.join(the_coqs_full_list)

    moleskine_formatted = parse_moleskin_users(moleskine, client)

    logger.info(result)

    chan = destination
    if chan == 'THE_AO':
        chan = the_ao

    logger.info('Channel to post to will be {} because the selected destination value was {} while the selected AO in the modal was {}'.format(
        chan, destination, the_ao))

    ao_name = get_channel_name(the_ao, logger, client)
    q_name, q_url = (get_user_names([the_q], logger, client, return_urls=True))
    q_name = (q_name or [''])[0]
    # print(f'CoQ: {the_coq}')
    q_url = q_url[0]
    pax_names = ', '.join(get_user_names(pax, logger, client, return_urls=False) or [''])

    msg = ""
    try:
        # formatting a message
        # todo: change to use json object
        header_msg = f"*Slackblast*: "
        title_msg = f"*" + title + "*"

        date_msg = f"*DATE*: " + the_date
        ao_msg = f"*AO*: <#" + the_ao + ">"
        q_msg = f"*Q*: <@" + the_q + ">" + the_coqs_formatted
        pax_msg = f"*PAX*: " + pax_formatted
        fngs_msg = f"*FNGs*: " + fngs_formatted
        count_msg = f"*COUNT*: " + count
        moleskine_msg = moleskine_formatted

        # Message the user via the app/bot name
        # if config('POST_TO_CHANNEL', cast=bool):
        body = make_body(date_msg, ao_msg, q_msg, pax_msg,
                            fngs_msg, count_msg, moleskine_msg)
        msg = header_msg + "\n" + title_msg + "\n" + body
        client.chat_postMessage(channel=chan, text=msg, username=f'{q_name} (via Slackblast)', icon_url=q_url)
        logger.info('\nMessage posted to Slack! \n{}'.format(msg))
    except Exception as slack_bolt_err:
        logger.error('Error with posting Slack message with chat_postMessage: {}'.format(
            slack_bolt_err))
        # Try again and bomb out without attempting to send email
        client.chat_postMessage(channel=chan, text='There was an error with your submission: {}'.format(slack_bolt_err))
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
            # sendmail.send(subject=subject, recipient=email_to, body=body_email)

            logger.info('\nEmail Sent! \n{}'.format(body_email))
    # except UndefinedValueError as email_not_configured_error:
    #     logger.info('Skipping sending email since no EMAIL_USER or EMAIL_PWD found. {}'.format(
    #         email_not_configured_error))
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

@slack_app.view("preblast-id")
def view_preblast_submission(ack, body, logger, client):
    ack()
    result = body["view"]["state"]["values"]
    title = result["title"]["title"]["value"]
    date = result["date"]["datepicker-action"]["selected_date"]
    the_time = result["time"]["time-action"]["value"]
    the_ao = result["the_ao"]["channels_select-action"]["selected_channel"]
    the_q = result["the_q"]["users_select-action"]["selected_user"]
    # the_coq = result["the_coq"]["multi_users_select-action"]["selected_user"]
    the_why = result["why"]["why-action"]["value"]
    coupon = result["coupon"]["coupon-action"]["value"]
    fngs = result["fngs"]["fng-action"]["value"]

    moleskine = result["moleskine"]["plain_text_input-action"]["value"]
    destination = result["destination"]["destination-input"]["selected_option"]["value"]
    email_to = safeget(result, "email", "email-action", "value")
    the_date = result["date"]["datepicker-action"]["selected_date"]

    logger.info(result)

    chan = destination
    if chan == 'THE_AO':
        chan = the_ao

    logger.info('Channel to post to will be {} because the selected destination value was {} while the selected AO in the modal was {}'.format(
        chan, destination, the_ao))

    ao_name = get_channel_name(the_ao, logger, client)
    q_name, q_url = (get_user_names([the_q], logger, client, return_urls=True))
    q_name = (q_name or [''])[0]
    q_url = q_url[0]

    # if the_coq == []:
    #     the_coqs_formatted = ''
    # else:
    #     the_coqs_formatted = get_pax(the_coq)
    #     the_coqs_full_list = [the_coqs_formatted]
    #     the_coqs_formatted = ', ' + ', '.join(the_coqs_full_list)

    msg = ""
    try:
        # formatting a message
        # todo: change to use json object
        header_msg = f"*Preblast: " + title + "*"
        date_msg = f"*Date*: " + the_date
        time_msg = f"*Time*: " + the_time
        ao_msg = f"*Where*: <#" + the_ao + ">"
        q_msg = f"*Q*: <@" + the_q + ">" # + the_coqs_formatted
        why_msg = f"*Why*: " + the_why
        coupon_msg = f"*Coupons*: " + coupon
        fngs_msg = f"*FNGs*: " + fngs
        moleskine_msg = moleskine

        # Message the user via the app/bot name
        # if config('POST_TO_CHANNEL', cast=bool):
        body_list = [date_msg, time_msg, ao_msg, q_msg]
        if the_why != 'None':
            body_list.append(why_msg)
        if coupon != 'None':
            body_list.append(coupon_msg)
        if fngs != 'None':
            body_list.append(fngs_msg)
        if moleskine != 'None':
            body_list.append(moleskine_msg)

        body = "\n".join(body_list)
        # body = make_preblast_body(date_msg, time_msg, ao_msg, q_msg, why_msg, coupon_msg,
        #                     fngs_msg, moleskine_msg)
        msg = header_msg + "\n" + body
        client.chat_postMessage(channel=chan, text=msg, username=f'{q_name} (via Slackblast)', icon_url=q_url)
        logger.info('\nMessage posted to Slack! \n{}'.format(msg))
    except Exception as slack_bolt_err:
        logger.error('Error with posting Slack message with chat_postMessage: {}'.format(
            slack_bolt_err))
        # Try again and bomb out without attempting to send email
        client.chat_postMessage(channel=chan, text='There was an error with your submission: {}'.format(slack_bolt_err))
    # try:
    #     if email_to and email_to != OPTIONAL_INPUT_VALUE:
    #         subject = title

    #         date_msg = f"DATE: " + the_date
    #         time_msg = f"TIME: " + the_time
    #         ao_msg = f"AO: " + (ao_name or '').replace('the', '').title()
    #         q_msg = f"Q: " + q_name
    #         why_msg = f"Why: " + pax_names
    #         coupon_msg = f"Coupon: " + coupon
    #         fngs_msg = f"FNGs: " + fngs
    #         moleskine_msg = moleskine

    #         body_email = make_preblast_body(date_msg, time_msg, ao_msg, q_msg, why_msg, coupon_msg,
    #                          fngs_msg, moleskine_msg)
    #         sendmail.send(subject=subject, recipient=email_to, body=body_email)

    #         logger.info('\nEmail Sent! \n{}'.format(body_email))
    # except UndefinedValueError as email_not_configured_error:
    #     logger.info('Skipping sending email since no EMAIL_USER or EMAIL_PWD found. {}'.format(
    #         email_not_configured_error))
    # except Exception as sendmail_err:
    #     logger.error('Error with sendmail: {}'.format(sendmail_err))


def make_preblast_body(date, time, ao, q, why, coupon, fngs, moleskine):
    return date + \
        "\n" + time + \
        "\n" + ao + \
        "\n" + q + \
        "\n" + why + \
        "\n" + coupon + \
        "\n" + fngs + \
        "\n" + moleskine


# @slack_app.options("es_categories")
# def show_categories(ack, body, logger):
#     ack()
#     lookup = body["value"]
#     filtered = [x for x in categories if lookup.lower() in x["name"].lower()]
#     output = formatted_categories(filtered)
#     options = output
#     logger.info(options)

#     ack(options=options)


def get_pax(pax):
    p = ""
    for x in pax:
        p += "<@" + x + "> "
    return p


def handler(event, context):
    print(f'Original event: {event}')
    print(f'Original context: {context}')
    # parsed_event = json.loads(event['body'])
    # team_id = parsed_event['team_id']
    # print(f'Team ID: {team_id}')
    slack_handler = SlackRequestHandler(app=slack_app)
    return slack_handler.handle(event, context)

