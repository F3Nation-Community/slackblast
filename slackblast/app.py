import json
from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from slack_sdk.web import WebClient
from utilities.helper_functions import (
    get_oauth_flow,
    handle_backblast_post,
    safe_get,
    handle_preblast_post,
    handle_config_post,
    handle_backblast_edit_post,
    get_paxminer_schema,
    replace_slack_user_ids,
)
from utilities import constants
from utilities.slack import forms
from utilities.slack import orm as slack_orm, actions
import logging
from logging import Logger
from datetime import datetime, date
from utilities.database import DbManager
from utilities.database.orm import Region
from utilities import builders
import os
import re
import copy

logger = logging.getLogger()
logger.setLevel(logging.INFO)

app = App(process_before_response=True, oauth_flow=get_oauth_flow())


def handler(event, context):
    slack_handler = SlackRequestHandler(app=app)
    return slack_handler.handle(event, context)


def respond_to_command(
    ack,
    body,
    logger,
    client,
    context,
):
    ack()
    logger.info("body is {}".format(body))
    logger.info("context is {}".format(context))

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    team_domain = safe_get(body, "team_domain") or safe_get(body, "team", "domain")
    trigger_id = safe_get(body, "trigger_id")
    channel_id = safe_get(body, "channel_id")

    region_record: Region = DbManager.get_record(Region, id=team_id)
    if not region_record:
        try:
            team_info = client.team_info()
            team_name = team_info["team"]["name"]
        except Exception as error:
            team_name = team_domain
        paxminer_schema = get_paxminer_schema(team_id, logger)
        region_record: Region = DbManager.create_record(
            Region(
                team_id=team_id,
                bot_token=context["bot_token"],
                workspace_name=team_name,
                paxminer_schema=paxminer_schema,
                email_enabled=0,
                email_option_show=0,
            )
        )

    if safe_get(body, "command") == "/config-slackblast":
        builders.build_config_form(client, trigger_id, region_record, logger)

    elif (
        safe_get(body, "command") == "/slackblast"
        or safe_get(body, "command") == "/backblast"
        # or initial_backblast_data
    ):
        builders.build_backblast_form(
            user_id,
            channel_id,
            body,
            client,
            logger,
            region_record,
            backblast_method="create",
            trigger_id=trigger_id,
        )

    elif safe_get(body, "command") == "/preblast":
        preblast_form = copy.deepcopy(forms.PREBLAST_FORM)
        preblast_form.set_options(
            {
                actions.PREBLAST_DESTINATION: slack_orm.as_selector_options(
                    names=["The AO Channel", "My DMs"], values=["The_AO", user_id]
                )
            }
        )
        preblast_form.set_initial_values(
            {
                actions.PREBLAST_Q: user_id,
                actions.PREBLAST_DATE: datetime.now().strftime("%Y-%m-%d"),
                actions.PREBLAST_DESTINATION: "The_AO",
            }
        )
        if channel_id:
            preblast_form.set_initial_values({actions.PREBLAST_AO: channel_id})
        preblast_form.post_modal(
            client=client,
            trigger_id=trigger_id,
            callback_id=actions.PREBLAST_CALLBACK_ID,
            title_text="Preblast",
        )


def respond_to_view(ack, body, client, logger, context):
    ack()
    logger.info("body is {}".format(body))
    logger.info("context is {}".format(context))

    if safe_get(body, "view", "callback_id") == actions.BACKBLAST_CALLBACK_ID:
        backblast_data: dict = forms.BACKBLAST_FORM.get_selected_values(body)
        logger.info("backblast_data is {}".format(backblast_data))
        handle_backblast_post(ack, body, logger, client, context, backblast_data)

    elif safe_get(body, "view", "callback_id") == actions.PREBLAST_CALLBACK_ID:
        preblast_data: dict = forms.PREBLAST_FORM.get_selected_values(body)
        logger.info("preblast_data is {}".format(preblast_data))
        handle_preblast_post(ack, body, logger, client, context, preblast_data)

    elif safe_get(body, "view", "callback_id") == actions.CONFIG_CALLBACK_ID:
        config_data: dict = forms.CONFIG_FORM.get_selected_values(body)
        logger.info("config_data is {}".format(config_data))
        handle_config_post(ack, body, logger, client, context, config_data)

    elif safe_get(body, "view", "callback_id") == actions.BACKBLAST_EDIT_CALLBACK_ID:
        backblast_data: dict = forms.BACKBLAST_FORM.get_selected_values(body)
        logger.info("backblast_data is {}".format(backblast_data))
        handle_backblast_edit_post(ack, body, logger, client, context, backblast_data)


@app.action(actions.BACKBLAST_EDIT_BUTTON)
def handle_backblast_edit(ack, body, client, logger, context, say):
    ack()
    logger.info("body is {}".format(body))
    logger.info("context is {}".format(context))
    backblast_data: dict = json.loads(body["actions"][0]["value"])
    if not safe_get(backblast_data, actions.BACKBLAST_MOLESKIN):
        backblast_data[actions.BACKBLAST_MOLESKIN] = body["message"]["blocks"][1]["text"]["text"]
        backblast_data[actions.BACKBLAST_MOLESKIN] = replace_slack_user_ids(
            backblast_data[actions.BACKBLAST_MOLESKIN], client, logger
        )
    logger.info("backblast_data is {}".format(backblast_data))

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    trigger_id = safe_get(body, "trigger_id")
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")
    region_record: Region = DbManager.get_record(Region, id=team_id)

    user_info_dict = client.users_info(user=user_id)
    user_admin: bool = user_info_dict["user"]["is_admin"]
    allow_edit: bool = (
        (region_record.editing_locked == 0)
        or user_admin
        or (user_id == backblast_data[actions.BACKBLAST_Q])
        or (user_id in backblast_data[actions.BACKBLAST_COQ] or [])
        or (user_id in backblast_data[actions.BACKBLAST_OP])
    )

    if allow_edit:
        builders.build_backblast_form(
            user_id=user_id,
            channel_id=channel_id,
            body=body,
            client=client,
            logger=logger,
            region_record=region_record,
            backblast_method="edit",
            trigger_id=trigger_id,
            initial_backblast_data=backblast_data,
        )
    else:
        client.chat_postEphemeral(
            text="Editing this backblast is only allowed for the Q(s), the original poster, or your local Slack admins. Please contact one of them to make changes.",
            channel=channel_id,
            user=user_id,
        )


@app.action(actions.BACKBLAST_NEW_BUTTON)
def handle_backblast_new(ack, body, client, logger, context):
    ack()
    logger.info("body is {}".format(body))
    logger.info("context is {}".format(context))

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    team_domain = safe_get(body, "team_domain") or safe_get(body, "team", "domain")
    trigger_id = safe_get(body, "trigger_id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")

    region_record: Region = DbManager.get_record(Region, id=team_id)
    if not region_record:
        try:
            team_info = client.team_info()
            team_name = team_info["team"]["name"]
        except Exception as error:
            team_name = team_domain
        paxminer_schema = get_paxminer_schema(team_id, logger)
        region_record: Region = DbManager.create_record(
            Region(
                team_id=team_id,
                bot_token=context["bot_token"],
                workspace_name=team_name,
                paxminer_schema=paxminer_schema,
                email_enabled=0,
                email_option_show=0,
            )
        )

    builders.build_backblast_form(
        user_id,
        channel_id,
        body,
        client,
        logger,
        region_record,
        backblast_method="create",
        trigger_id=trigger_id,
    )


@app.action(actions.BACKBLAST_AO)
@app.action(actions.BACKBLAST_Q)
@app.action(actions.BACKBLAST_DATE)
def handle_duplicate_check(ack, body, client, logger, context):
    ack()
    logger.info("body is {}".format(body))
    logger.info("context is {}".format(context))
    view_id = safe_get(body, "container", "view_id")

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    trigger_id = safe_get(body, "trigger_id")
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    channel_id = safe_get(body, "channel_id")
    region_record: Region = DbManager.get_record(Region, id=team_id)

    currently_duplicate = False
    for block in body["view"]["blocks"]:
        if block["block_id"] == actions.BACKBLAST_DUPLICATE_WARNING:
            currently_duplicate = True
            break

    if safe_get(body, "view", "callback_id") == actions.BACKBLAST_EDIT_CALLBACK_ID:
        backblast_method = "edit"
        parent_metadata = body["view"]["blocks"][-1]["elements"][0]["text"]
    else:
        backblast_method = "create"
        parent_metadata = None

    backblast_data = forms.BACKBLAST_FORM.get_selected_values(body)
    logger.info("backblast_data is {}".format(backblast_data))

    builders.build_backblast_form(
        user_id=user_id,
        channel_id=channel_id,
        body=body,
        client=client,
        logger=logger,
        region_record=region_record,
        backblast_method=backblast_method,
        trigger_id=trigger_id,
        initial_backblast_data=backblast_data,
        currently_duplicate=currently_duplicate,
        update_view_id=view_id,
        duplicate_check=True,
        parent_metadata=parent_metadata,
    )


@app.action(actions.CONFIG_EMAIL_ENABLE)
def handle_config_email_enable(ack, body, client, logger, context):
    ack()
    logger.info("body is {}".format(body))
    logger.info("context is {}".format(context))
    view_id = safe_get(body, "container", "view_id")

    trigger_id = safe_get(body, "trigger_id")
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    region_record: Region = DbManager.get_record(Region, id=team_id)

    config_data = forms.CONFIG_FORM.get_selected_values(body)
    logger.info("config_data is {}".format(config_data))

    builders.build_config_form(
        client=client,
        trigger_id=trigger_id,
        region_record=region_record,
        logger=logger,
        initial_config_data=config_data,
        update_view_id=view_id,
    )


COMMAND_KWARGS = {}
COMMAND_ARGS = []
VIEW_KWARGS = {}
VIEW_ARGS = []
if constants.LOCAL_DEVELOPMENT:
    COMMAND_ARGS = [respond_to_command]
    VIEW_ARGS = [respond_to_view]
else:
    COMMAND_KWARGS["ack"] = lambda ack: ack()
    COMMAND_KWARGS["lazy"] = [respond_to_command]
    VIEW_KWARGS["ack"] = lambda ack: ack()
    VIEW_KWARGS["lazy"] = [respond_to_view]

MATCH_ALL_PATTERN = re.compile(".*")

# Command handlers
app.command(MATCH_ALL_PATTERN)(*COMMAND_ARGS, **COMMAND_KWARGS)

app.view(MATCH_ALL_PATTERN)(*VIEW_ARGS, **VIEW_KWARGS)
