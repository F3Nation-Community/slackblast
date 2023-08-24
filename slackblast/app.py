import json
from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from slack_sdk.web import WebClient
from utilities.helper_functions import (
    get_channel_name,
    get_oauth_flow,
    safe_get,
    get_paxminer_schema,
    replace_slack_user_ids,
    get_region_record,
)
from utilities.handlers import handle_backblast_post, handle_preblast_post, handle_config_post
from utilities import constants
from utilities.slack import forms
from utilities.slack import orm as slack_orm, actions
import logging
from logging import Logger
from datetime import datetime, date
from utilities.database import DbManager
from utilities.database.orm import Region
from utilities import builders, strava
import os
import re
import copy
from pprint import pformat

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

app = App(process_before_response=True, oauth_flow=get_oauth_flow())


def handler(event, context):
    if event.get("path") == "/exchange_token":
        return strava.strava_exchange_token(event, context)
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
    logger.debug("body is {}".format(body))
    logger.debug("context is {}".format(context))

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    team_domain = safe_get(body, "team_domain") or safe_get(body, "team", "domain")
    trigger_id = safe_get(body, "trigger_id")
    channel_id = safe_get(body, "channel_id")
    channel_name = safe_get(body, "channel_name")

    region_record = get_region_record(team_id, body, context, client, logger)

    if safe_get(body, "command") == "/config-slackblast":
        builders.build_config_form(client, trigger_id, region_record, logger)

    elif safe_get(body, "command") == "/slackblast" or safe_get(body, "command") == "/backblast":
        builders.build_backblast_form(
            user_id=user_id,
            channel_id=channel_id,
            channel_name=channel_name,
            body=body,
            client=client,
            logger=logger,
            region_record=region_record,
            backblast_method="create",
            trigger_id=trigger_id,
        )

    elif safe_get(body, "command") == "/preblast":
        builders.build_preblast_form(
            user_id,
            channel_id,
            client,
            trigger_id,
            region_record,
        )


def respond_to_view(ack, body, client, logger, context):
    ack()
    logger.debug("body is {}".format(body))
    logger.debug("context is {}".format(context))

    if safe_get(body, "view", "callback_id") in [
        actions.BACKBLAST_CALLBACK_ID,
        actions.BACKBLAST_EDIT_CALLBACK_ID,
    ]:
        backblast_data: dict = forms.BACKBLAST_FORM.get_selected_values(body)
        logger.debug("backblast_data is {}".format(backblast_data))

        if safe_get(body, "view", "callback_id") == actions.BACKBLAST_CALLBACK_ID:
            create_or_edit = "create"
        else:
            create_or_edit = "edit"
        handle_backblast_post(ack, body, logger, client, context, backblast_data, create_or_edit)

    elif safe_get(body, "view", "callback_id") == actions.PREBLAST_CALLBACK_ID:
        preblast_data: dict = forms.PREBLAST_FORM.get_selected_values(body)
        logger.debug("preblast_data is {}".format(preblast_data))
        handle_preblast_post(ack, body, logger, client, context, preblast_data)

    elif safe_get(body, "view", "callback_id") == actions.CONFIG_CALLBACK_ID:
        config_data: dict = forms.CONFIG_FORM.get_selected_values(body)
        logger.debug("config_data is {}".format(config_data))
        handle_config_post(ack, body, logger, client, context, config_data)

    elif safe_get(body, "view", "callback_id") == actions.STRAVA_MODIFY_CALLBACK_ID:
        strava_data: dict = forms.STRAVA_ACTIVITY_MODIFY_FORM.get_selected_values(body)
        logger.debug("strava_data is {}".format(strava_data))
        strava.handle_strava_modify(ack, body, logger, client, context, strava_data)


@app.action(actions.BACKBLAST_EDIT_BUTTON)
def handle_backblast_edit(ack, body, client, logger, context, say):
    ack()
    logger.debug("body is {}".format(body))
    logger.debug("context is {}".format(context))

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    trigger_id = safe_get(body, "trigger_id")
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")
    channel_name = safe_get(body, "channel_name") or safe_get(body, "channel", "name")
    region_record: Region = DbManager.get_record(Region, id=team_id)

    backblast_data: dict = json.loads(body["actions"][0]["value"])
    if not safe_get(backblast_data, actions.BACKBLAST_MOLESKIN):
        backblast_data[actions.BACKBLAST_MOLESKIN] = body["message"]["blocks"][1]["text"]["text"]
        backblast_data[actions.BACKBLAST_MOLESKIN] = replace_slack_user_ids(
            backblast_data[actions.BACKBLAST_MOLESKIN], client, logger, region_record
        )
    logger.debug("backblast_data is {}".format(backblast_data))

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
            channel_name=channel_name,
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
    logger.debug("body is {}".format(body))
    logger.debug("context is {}".format(context))

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    trigger_id = safe_get(body, "trigger_id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")
    channel_name = safe_get(body, "channel_name") or safe_get(body, "channel", "name")

    region_record: Region = get_region_record(team_id, body, context, client, logger)

    builders.build_backblast_form(
        user_id=user_id,
        channel_id=channel_id,
        channel_name=channel_name,
        body=body,
        client=client,
        logger=logger,
        region_record=region_record,
        backblast_method="create",
        trigger_id=trigger_id,
    )


@app.action(actions.BACKBLAST_STRAVA_BUTTON)
def handle_backblast_strava(ack, body, client, logger, context):
    ack()

    logger.info("body is \n{}".format(pformat(body)))
    logger.info("context is \n{}".format(pformat(context)))

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    trigger_id = safe_get(body, "trigger_id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")
    channel_name = safe_get(body, "channel_name") or safe_get(body, "channel", "name")
    lambda_function_host = safe_get(context, "lambda_request", "headers", "Host")

    builders.build_strava_form(
        team_id=team_id,
        user_id=user_id,
        client=client,
        body=body,
        trigger_id=trigger_id,
        channel_id=channel_id,
        logger=logger,
        lambda_function_host=lambda_function_host,
    )


@app.action(re.compile(actions.STRAVA_ACTIVITY_BUTTON))
def handle_strava_activity_action(ack, body, logger, client, context):
    ack()
    logger.info(body)
    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    view_id = safe_get(body, "container", "view_id")
    trigger_id = safe_get(body, "trigger_id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")

    strava_activity_id, channel_id, backblast_ts, backblast_title, backblast_moleskine = body[
        "actions"
    ][0]["value"].split("|")

    metadata = {
        "strava_activity_id": strava_activity_id,
        "channel_id": channel_id,
        "backblast_ts": backblast_ts,
    }

    builders.build_strava_modify_form(
        client=client,
        logger=logger,
        trigger_id=trigger_id,
        backblast_title=backblast_title,
        backblast_moleskine=backblast_moleskine,
        backblast_metadata=metadata,
        view_id=view_id,
    )


@app.action(actions.BACKBLAST_AO)
@app.action(actions.BACKBLAST_Q)
@app.action(actions.BACKBLAST_DATE)
def handle_duplicate_check(ack, body, client, logger, context):
    ack()
    logger.debug("body is {}".format(body))
    logger.debug("context is {}".format(context))
    view_id = safe_get(body, "container", "view_id")

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    trigger_id = safe_get(body, "trigger_id")
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    channel_id = safe_get(body, "channel_id")
    channel_name = safe_get(body, "channel_name")
    region_record: Region = DbManager.get_record(Region, id=team_id)

    currently_duplicate = False
    for block in body["view"]["blocks"]:
        if block["block_id"] == actions.BACKBLAST_DUPLICATE_WARNING:
            currently_duplicate = True
        if not channel_id and block["block_id"] == actions.BACKBLAST_DESTINATION:
            channel_id = block["element"]["options"][1]["value"]
            channel_name = get_channel_name(channel_id, logger, client, region_record)

    if safe_get(body, "view", "callback_id") == actions.BACKBLAST_EDIT_CALLBACK_ID:
        backblast_method = "edit"
        parent_metadata = json.loads(body["view"]["private_metadata"])
    else:
        backblast_method = "create"
        parent_metadata = None

    backblast_data = forms.BACKBLAST_FORM.get_selected_values(body)
    logger.debug("backblast_data is {}".format(backblast_data))

    builders.build_backblast_form(
        user_id=user_id,
        channel_id=channel_id,
        channel_name=channel_name,
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
    logger.debug("body is {}".format(body))
    logger.debug("context is {}".format(context))
    view_id = safe_get(body, "container", "view_id")

    trigger_id = safe_get(body, "trigger_id")
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    region_record: Region = DbManager.get_record(Region, id=team_id)

    config_data = forms.CONFIG_FORM.get_selected_values(body)
    logger.debug("config_data is {}".format(config_data))

    builders.build_config_form(
        client=client,
        trigger_id=trigger_id,
        region_record=region_record,
        logger=logger,
        initial_config_data=config_data,
        update_view_id=view_id,
    )


@app.action(actions.STRAVA_CONNECT_BUTTON)
def handle_some_action(ack, body, logger):
    ack()
    logger.info(body)


@app.view_closed(actions.STRAVA_MODIFY_CALLBACK_ID)
def handle_view_closed_events(ack, body, logger, client, context):
    ack()
    logger.info(body)
    strava.handle_strava_modify(ack, body, logger, client, context, strava_data=None)


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
