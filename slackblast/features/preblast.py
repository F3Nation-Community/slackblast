import copy
import json
from datetime import datetime
from logging import Logger

import pytz
from slack_sdk.web import WebClient

from utilities.database.orm import SlackSettings
from utilities.helper_functions import (
    get_user_names,
    remove_keys_from_dict,
    safe_get,
)
from utilities.slack import actions, forms
from utilities.slack import orm as slack_orm


def build_preblast_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")

    update_view_id = safe_get(body, actions.LOADING_ID)
    preblast_form = copy.deepcopy(forms.PREBLAST_FORM)

    if (safe_get(body, "command") in ["/preblast"]) or (
        safe_get(body, "actions", 0, "action_id") == actions.PREBLAST_NEW_BUTTON
    ):
        preblast_method = "New"
        parent_metadata = {}
        preblast_metadata = None
        callback_id = actions.PREBLAST_CALLBACK_ID
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
                actions.PREBLAST_DATE: datetime.now(pytz.timezone("US/Central")).strftime("%Y-%m-%d"),
                actions.PREBLAST_DESTINATION: "The_AO",
                actions.PREBLAST_MOLESKIN: region_record.preblast_moleskin_template or "",
            }
        )
        if channel_id:
            preblast_form.set_initial_values({actions.PREBLAST_AO: channel_id})
    else:
        preblast_method = "Edit"
        parent_metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
        preblast_metadata = parent_metadata or {
            "channel_id": safe_get(body, "container", "channel_id"),
            "message_ts": safe_get(body, "container", "message_ts"),
        }
        callback_id = actions.PREBLAST_EDIT_CALLBACK_ID
        preblast_form.delete_block(actions.PREBLAST_DESTINATION)
        initial_preblast_data = safe_get(body, "message", "metadata", "event_payload") or json.loads(
            safe_get(body, "actions", 0, "value") or "{}"
        )
        blocks = safe_get(body, "message", "blocks")
        moleskin_block = remove_keys_from_dict(blocks[1], ["display_url", "display_team_id"])
        if len(blocks) == 3:
            initial_preblast_data[actions.PREBLAST_MOLESKIN] = moleskin_block
        preblast_form.set_initial_values(initial_preblast_data)

    preblast_form.update_modal(
        client=client,
        view_id=update_view_id,
        callback_id=callback_id,
        title_text=f"{preblast_method} Preblast",
        parent_metadata=preblast_metadata,
    )


def handle_preblast_post(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    create_or_edit = "create" if safe_get(body, "view", "callback_id") == actions.PREBLAST_CALLBACK_ID else "edit"

    preblast_data = forms.PREBLAST_FORM.get_selected_values(body)
    preblast_data[actions.PREBLAST_OP] = safe_get(body, "user_id") or safe_get(body, "user", "id")

    title = safe_get(preblast_data, actions.PREBLAST_TITLE)
    the_date = safe_get(preblast_data, actions.PREBLAST_DATE)
    the_time = safe_get(preblast_data, actions.PREBLAST_TIME)
    the_ao = safe_get(preblast_data, actions.PREBLAST_AO)
    the_q = safe_get(preblast_data, actions.PREBLAST_Q)
    the_why = safe_get(preblast_data, actions.PREBLAST_WHY)
    fngs = safe_get(preblast_data, actions.PREBLAST_FNGS)
    coupons = safe_get(preblast_data, actions.PREBLAST_COUPONS)
    moleskin = safe_get(preblast_data, actions.PREBLAST_MOLESKIN)
    destination = safe_get(preblast_data, actions.PREBLAST_DESTINATION)

    chan = destination
    if chan == "The_AO":
        chan = the_ao

    if create_or_edit == "edit":
        message_metadata = json.loads(body["view"]["private_metadata"])
        message_channel = safe_get(message_metadata, "channel_id")
        message_ts = safe_get(message_metadata, "message_ts")
    else:
        message_channel = chan
        message_ts = None

    q_name, q_url = get_user_names([the_q], logger, client, return_urls=True)
    q_name = (q_name or [""])[0]
    q_url = q_url[0]

    header_msg = f"*Preblast: {title}*"
    date_msg = f"*Date*: {the_date}"
    time_msg = f"*Time*: {the_time}"
    ao_msg = f"*Where*: <#{the_ao}>"
    q_msg = f"*Q*: <@{the_q}>"  # + the_coqs_formatted

    body_list = [header_msg, date_msg, time_msg, ao_msg, q_msg]
    if the_why:
        body_list.append(f"*Why*: {the_why}")
    if coupons:
        body_list.append(f"*Coupons*: {coupons}")
    if fngs:
        body_list.append(f"*FNGs*: {fngs}")

    msg = "\n".join(body_list)

    msg_block = {
        "type": "section",
        "text": {"type": "mrkdwn", "text": msg},
        "block_id": "msg_text",
    }

    preblast_data.pop(actions.PREBLAST_MOLESKIN)
    action_block = {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":pencil: Edit this preblast",
                    "emoji": True,
                },
                "value": "edit",
                "action_id": actions.PREBLAST_EDIT_BUTTON,
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":heavy_plus_sign: New preblast",
                    "emoji": True,
                },
                "value": "new",
                "action_id": actions.PREBLAST_NEW_BUTTON,
            },
        ],
        "block_id": actions.PREBLAST_EDIT_BUTTON,
    }

    blocks = [msg_block]
    if moleskin:
        blocks.append(moleskin)
    blocks.append(action_block)

    if create_or_edit == "create":
        client.chat_postMessage(
            channel=chan,
            text=msg,
            username=f"{q_name} (via Slackblast)",
            icon_url=q_url,
            blocks=blocks,
            metadata={"event_type": "backblast", "event_payload": preblast_data},
        )
        logger.debug("\nPreblast posted to Slack! \n{}".format(msg))
        print(json.dumps({"event_type": "successful_preblast_create", "team_name": region_record.workspace_name}))
    elif create_or_edit == "edit":
        client.chat_update(
            channel=message_channel,
            ts=message_ts,
            text=msg,
            username=f"{q_name} (via Slackblast)",
            icon_url=q_url,
            blocks=blocks,
        )
        logger.debug("\nPreblast updated in Slack! \n{}".format(msg))
        print(json.dumps({"event_type": "successful_preblast_edit", "team_name": region_record.workspace_name}))


def handle_preblast_edit_button(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")

    preblast_data = safe_get(body, "message", "metadata", "event_payload") or json.loads(
        safe_get(body, "actions", 0, "value") or "{}"
    )

    user_info_dict = client.users_info(user=user_id)
    user_admin: bool = user_info_dict["user"]["is_admin"]
    allow_edit: bool = (
        (region_record.editing_locked == 0)
        or user_admin
        or (user_id == preblast_data[actions.PREBLAST_Q])
        or (user_id in preblast_data[actions.PREBLAST_OP])
    )

    if allow_edit:
        build_preblast_form(
            body=body,
            client=client,
            logger=logger,
            context=context,
            region_record=region_record,
        )
    else:
        client.chat_postEphemeral(
            text="Editing this preblast is only allowed for the Q, the original poster, or your local Slack admins. "
            "Please contact one of them to make changes.",
            channel=channel_id,
            user=user_id,
        )
