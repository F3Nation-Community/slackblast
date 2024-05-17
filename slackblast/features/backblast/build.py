import copy
import json
from datetime import datetime
from logging import Logger

import pytz
from slack_sdk.web import WebClient

from features.backblast import add_custom_field_blocks, ui
from utilities import constants
from utilities.database.orm import Region
from utilities.helper_functions import (
    check_for_duplicate,
    get_channel_name,
    plain_text_to_rich_block,
    safe_get,
)
from utilities.slack import actions
from utilities.slack import orm as slack_orm


def build_backblast_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    """This function builds the backblast form and posts it to Slack. There are several entry points for this function:
        1. Building a new backblast, either through the /backblast command or the "New Backblast" button
        2. Editing an existing backblast, invoked by the "Edit Backblast" button
        3. Duplicate checking, invoked by the "Q", "Date", or "AO" fields being changed

    Args:
        body (dict): Slack request body
        client (WebClient): Slack WebClient object
        logger (Logger): Logger object
        context (dict): Slack request context
        region_record (Region): Region record for the requesting region
    """

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")
    channel_name = safe_get(body, "channel_name") or safe_get(body, "channel", "name")
    trigger_id = safe_get(body, "trigger_id")

    for block in safe_get(body, "view", "blocks") or []:
        if not channel_id and block["block_id"] == actions.BACKBLAST_DESTINATION:
            channel_id = block["element"]["options"][1]["value"]
            channel_name = get_channel_name(channel_id, logger, client, region_record)

    if (
        (safe_get(body, "command") in ["/backblast", "/slackblast"])
        or (safe_get(body, "actions", 0, "action_id") == actions.BACKBLAST_NEW_BUTTON)
        or (safe_get(body, "view", "callback_id") == actions.BACKBLAST_CALLBACK_ID)
    ):
        backblast_method = "create"
        update_view_id = safe_get(body, actions.LOADING_ID)
        duplicate_check = False
        parent_metadata = {}
    else:
        backblast_method = "edit"
        update_view_id = (
            safe_get(body, "view", "id") or safe_get(body, "container", "view_id") or safe_get(body, actions.LOADING_ID)
        )
        duplicate_check = safe_get(body, "view", "callback_id") == actions.BACKBLAST_EDIT_CALLBACK_ID
        parent_metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")

    if safe_get(body, "actions", 0, "action_id") in [
        actions.BACKBLAST_AO,
        actions.BACKBLAST_DATE,
        actions.BACKBLAST_Q,
    ]:
        logger.debug("running duplicate check")
        duplicate_check = True
        update_view_id = safe_get(body, "view", "id") or safe_get(body, "container", "view_id")
        initial_backblast_data = ui.BACKBLAST_FORM.get_selected_values(body)
    elif (safe_get(body, "view", "callback_id") == actions.BACKBLAST_EDIT_CALLBACK_ID) or (
        safe_get(body, "actions", 0, "action_id") == actions.BACKBLAST_EDIT_BUTTON
    ):
        initial_backblast_data = safe_get(body, "message", "metadata", "event_payload") or json.loads(
            safe_get(body, "actions", 0, "value") or "{}"
        )
        if not safe_get(initial_backblast_data, actions.BACKBLAST_MOLESKIN):
            moleskin_block = safe_get(body, "message", "blocks", 1)
            if moleskin_block.get("type") == "section":
                initial_backblast_data[actions.BACKBLAST_MOLESKIN] = plain_text_to_rich_block(
                    moleskin_block["text"]["text"]
                )
            else:
                initial_backblast_data[actions.BACKBLAST_MOLESKIN] = moleskin_block
            # initial_backblast_data[actions.BACKBLAST_MOLESKIN] = replace_slack_user_ids(
            #     initial_backblast_data[actions.BACKBLAST_MOLESKIN], client, logger, region_record
            # )
    else:
        initial_backblast_data = None

    backblast_form = copy.deepcopy(ui.BACKBLAST_FORM)

    if backblast_method == "edit" or duplicate_check:
        og_ts = safe_get(body, "message", "ts") or safe_get(parent_metadata, "message_ts")
        is_duplicate = check_for_duplicate(
            q=safe_get(initial_backblast_data, actions.BACKBLAST_Q),
            date=safe_get(initial_backblast_data, actions.BACKBLAST_DATE),
            ao=safe_get(initial_backblast_data, actions.BACKBLAST_AO),
            region_record=region_record,
            logger=logger,
            og_ts=og_ts,
        )
        ao_id = safe_get(initial_backblast_data, actions.BACKBLAST_AO)
        ao_name = get_channel_name(ao_id, logger, client, region_record)
    else:
        is_duplicate = check_for_duplicate(
            q=user_id,
            date=datetime.now(pytz.timezone("US/Central")).date(),
            ao=channel_id,
            region_record=region_record,
            logger=logger,
        )
        ao_id = channel_id
        ao_name = channel_name

    backblast_form = add_custom_field_blocks(backblast_form, region_record)

    logger.debug("is_duplicate is {}".format(is_duplicate))
    logger.debug("backblast_form is {}".format(backblast_form.blocks))
    if not is_duplicate:
        backblast_form.delete_block(actions.BACKBLAST_DUPLICATE_WARNING)

    if backblast_method == "edit" or duplicate_check:
        backblast_form.set_initial_values(initial_backblast_data)

    if backblast_method == "edit":
        backblast_metadata = parent_metadata or {
            "channel_id": safe_get(body, "container", "channel_id"),
            "message_ts": safe_get(body, "container", "message_ts"),
            "files": safe_get(initial_backblast_data, actions.BACKBLAST_FILE) or [],
        }

        backblast_form.delete_block(actions.BACKBLAST_EMAIL_SEND)
        backblast_form.delete_block(actions.BACKBLAST_DESTINATION)
        callback_id = actions.BACKBLAST_EDIT_CALLBACK_ID
    else:
        logger.debug("ao_id is {}".format(ao_id))
        logger.debug("channel_id is {}".format(channel_id))
        backblast_form.set_options(
            {
                actions.BACKBLAST_DESTINATION: slack_orm.as_selector_options(
                    names=[f"The AO Channel (#{ao_name})", f"Current Channel (#{channel_name})"],
                    values=["The_AO", channel_id],
                )
            }
        )
        if not (region_record.email_enabled & region_record.email_option_show):
            backblast_form.delete_block(actions.BACKBLAST_EMAIL_SEND)
        backblast_metadata = None
        callback_id = actions.BACKBLAST_CALLBACK_ID

    if backblast_method == "create":
        if (region_record.default_destination or "") == constants.CONFIG_DESTINATION_CURRENT["value"]:
            default_destination_id = channel_id
        elif (region_record.default_destination or "") == constants.CONFIG_DESTINATION_AO["value"]:
            default_destination_id = "The_AO"
        else:
            default_destination_id = None

        backblast_form.set_initial_values(
            {
                actions.BACKBLAST_Q: user_id,
                actions.BACKBLAST_DATE: datetime.now(pytz.timezone("US/Central")).strftime("%Y-%m-%d"),
                actions.BACKBLAST_DESTINATION: default_destination_id or "The_AO",
                actions.BACKBLAST_MOLESKIN: region_record.backblast_moleskin_template
                or constants.DEFAULT_BACKBLAST_MOLESKINE_TEMPLATE,
            }
        )
        if channel_id:
            backblast_form.set_initial_values({actions.BACKBLAST_AO: channel_id})
    logger.debug(backblast_form.blocks)
    logger.debug("backblast_form is {}".format(backblast_form.as_form_field()))

    if duplicate_check or update_view_id:
        backblast_form.update_modal(
            client=client,
            view_id=update_view_id,
            callback_id=callback_id,
            title_text="Backblast",
            parent_metadata=backblast_metadata,
        )
    else:
        backblast_form.post_modal(
            client=client,
            trigger_id=trigger_id,
            callback_id=callback_id,
            title_text="Backblast",
            parent_metadata=backblast_metadata,
        )
