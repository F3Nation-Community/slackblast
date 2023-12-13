import json
import os
from typing import List
import pytz

from slack_sdk.web import WebClient
from utilities.database.orm import Region, User
from utilities.database import DbManager
from utilities.slack import forms, orm as slack_orm, actions
from utilities import constants, strava
from utilities.helper_functions import (
    get_channel_name,
    replace_slack_user_ids,
    safe_get,
    check_for_duplicate,
)
import copy
from logging import Logger
from datetime import datetime
from cryptography.fernet import Fernet
from requests_oauthlib import OAuth2Session


def add_custom_field_blocks(form: slack_orm.BlockView, region_record: Region) -> slack_orm.BlockView:
    output_form = copy.deepcopy(form)
    for custom_field in (region_record.custom_fields or {}).values():
        if safe_get(custom_field, "enabled"):
            output_form.add_block(
                slack_orm.InputBlock(
                    element=forms.CUSTOM_FIELD_TYPE_MAP[custom_field["type"]],
                    action=actions.CUSTOM_FIELD_PREFIX + custom_field["name"],
                    label=custom_field["name"],
                    optional=True,
                )
            )
            if safe_get(custom_field, "type") == "Dropdown":
                output_form.set_options(
                    {
                        actions.CUSTOM_FIELD_PREFIX
                        + custom_field["name"]: slack_orm.as_selector_options(
                            names=custom_field["options"],
                            values=custom_field["options"],
                        )
                    }
                )
    return output_form


def build_backblast_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
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
        update_view_id = None
        duplicate_check = False
        parent_metadata = {}
    else:
        backblast_method = "edit"
        update_view_id = safe_get(body, "view", "id") or safe_get(body, "container", "view_id")
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
        initial_backblast_data = forms.BACKBLAST_FORM.get_selected_values(body)
    elif (safe_get(body, "view", "callback_id") == actions.BACKBLAST_EDIT_CALLBACK_ID) or (
        safe_get(body, "actions", 0, "action_id") == actions.BACKBLAST_EDIT_BUTTON
    ):
        initial_backblast_data = json.loads(safe_get(body, "actions", 0, "value") or "{}")
        if not safe_get(initial_backblast_data, actions.BACKBLAST_MOLESKIN):
            initial_backblast_data[actions.BACKBLAST_MOLESKIN] = safe_get(body, "message", "blocks", 1, "text", "text")
            initial_backblast_data[actions.BACKBLAST_MOLESKIN] = replace_slack_user_ids(
                initial_backblast_data[actions.BACKBLAST_MOLESKIN], client, logger, region_record
            )
    else:
        initial_backblast_data = None

    backblast_form = copy.deepcopy(forms.BACKBLAST_FORM)

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

    if duplicate_check:
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


def build_config_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    trigger_id = safe_get(body, "trigger_id")
    if safe_get(body, "command") == "/config-slackblast":
        initial_config_data = None
        update_view_id = None
    else:
        initial_config_data = forms.CONFIG_FORM.get_selected_values(body)
        update_view_id = safe_get(body, "view", "id") or safe_get(body, "container", "view_id")

    config_form = copy.deepcopy(forms.CONFIG_FORM)

    if region_record:
        if region_record.email_password:
            fernet = Fernet(os.environ[constants.PASSWORD_ENCRYPT_KEY].encode())
            email_password_decrypted = fernet.decrypt(region_record.email_password.encode()).decode()
        else:
            email_password_decrypted = "SamplePassword123!"

        # logger.debug("running fuzzy match")
        # schema_best_guesses = run_fuzzy_match(region_record.workspace_name)
        # schema_best_guesses.append("Other (enter below)")
        # config_form.set_options(
        #     {actions.CONFIG_PAXMINER_DB: slack_orm.as_selector_options(schema_best_guesses)}
        # )

        config_form.set_initial_values(
            {
                # actions.CONFIG_PAXMINER_DB: region_record.paxminer_schema,
                actions.CONFIG_EMAIL_ENABLE: "enable" if region_record.email_enabled == 1 else "disable",
                actions.CONFIG_EMAIL_SHOW_OPTION: "yes" if region_record.email_option_show == 1 else "no",
                actions.CONFIG_EMAIL_FROM: region_record.email_user or "example_sender@gmail.com",
                actions.CONFIG_EMAIL_TO: region_record.email_to or "example_destination@gmail.com",
                actions.CONFIG_EMAIL_SERVER: region_record.email_server or "smtp.gmail.com",
                actions.CONFIG_EMAIL_PORT: str(region_record.email_server_port or 587),
                actions.CONFIG_EMAIL_PASSWORD: email_password_decrypted,
                actions.CONFIG_POSTIE_ENABLE: "yes" if region_record.postie_format == 1 else "no",
                actions.CONFIG_EDITING_LOCKED: "yes" if region_record.editing_locked == 1 else "no",
                actions.CONFIG_DEFAULT_DESTINATION: region_record.default_destination
                or constants.CONFIG_DESTINATION_AO["value"],
                actions.CONFIG_BACKBLAST_MOLESKINE_TEMPLATE: constants.DEFAULT_BACKBLAST_MOLESKINE_TEMPLATE
                if region_record.backblast_moleskin_template is None
                else region_record.backblast_moleskin_template,
                actions.CONFIG_PREBLAST_MOLESKINE_TEMPLATE: ""
                if region_record.preblast_moleskin_template is None
                else region_record.preblast_moleskin_template,
                actions.CONFIG_ENABLE_STRAVA: "enable" if region_record.strava_enabled == 1 else "disable",
            }
        )

    if not initial_config_data:
        email_enable = "enable" if region_record.email_enabled == 1 else "disable"
    else:
        email_enable = initial_config_data[actions.CONFIG_EMAIL_ENABLE]

    logger.debug("email_enable is {}".format(email_enable))
    if email_enable == "disable":
        config_form.delete_block(actions.CONFIG_EMAIL_SHOW_OPTION)
        config_form.delete_block(actions.CONFIG_EMAIL_FROM)
        config_form.delete_block(actions.CONFIG_EMAIL_TO)
        config_form.delete_block(actions.CONFIG_EMAIL_SERVER)
        config_form.delete_block(actions.CONFIG_EMAIL_PORT)
        config_form.delete_block(actions.CONFIG_EMAIL_PASSWORD)
        config_form.delete_block(actions.CONFIG_POSTIE_ENABLE)
        config_form.delete_block(actions.CONFIG_PASSWORD_CONTEXT)
        config_form.delete_block(actions.CONFIG_POSTIE_CONTEXT)

    if update_view_id:
        config_form.update_modal(
            client=client,
            view_id=update_view_id,
            callback_id=actions.CONFIG_CALLBACK_ID,
            title_text="Configure Slackblast",
        )
    else:
        config_form.post_modal(
            client=client,
            trigger_id=trigger_id,
            callback_id=actions.CONFIG_CALLBACK_ID,
            title_text="Configure Slackblast",
        )


def ignore_event(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    logger.debug("Ignoring event")


def build_preblast_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")
    trigger_id = safe_get(body, "trigger_id")

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
        initial_preblast_data = json.loads(safe_get(body, "actions", 0, "value") or "{}")
        preblast_form.set_initial_values(initial_preblast_data)

    preblast_form.post_modal(
        client=client,
        trigger_id=trigger_id,
        callback_id=callback_id,
        title_text=f"{preblast_method} Preblast",
        parent_metadata=preblast_metadata,
    )


def build_strava_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    trigger_id = safe_get(body, "trigger_id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")
    lambda_function_host = safe_get(context, "lambda_request", "headers", "Host")

    backblast_ts = body["message"]["ts"]
    backblast_meta = json.loads(body["message"]["blocks"][-1]["elements"][0]["value"])
    moleskine_text = body["message"]["blocks"][1]["text"]["text"]

    allow_strava: bool = (
        (user_id == backblast_meta[actions.BACKBLAST_Q])
        or (user_id in backblast_meta[actions.BACKBLAST_COQ] or [])
        or (user_id in backblast_meta[actions.BACKBLAST_PAX])
        or (user_id in backblast_meta[actions.BACKBLAST_OP])
    )

    if allow_strava:
        user_records: List[User] = DbManager.find_records(
            User, filters=[User.user_id == user_id, User.team_id == team_id]
        )

        if len(user_records) == 0:
            title_text = "Connect Strava"
            redirect_stage = "" if constants.LOCAL_DEVELOPMENT else "Prod/"
            oauth = OAuth2Session(
                client_id=os.environ[constants.STRAVA_CLIENT_ID],
                redirect_uri=f"https://{lambda_function_host}/{redirect_stage}exchange_token",
                scope=["read,activity:read,activity:write"],
                state=f"{team_id}-{user_id}",
            )
            authorization_url, state = oauth.authorization_url("https://www.strava.com/oauth/authorize")
            strava_blocks = [
                slack_orm.ActionsBlock(
                    elements=[
                        slack_orm.ButtonElement(
                            label="Connect Strava Account",
                            action=actions.STRAVA_CONNECT_BUTTON,
                            url=authorization_url,
                        )
                    ]
                ),
                slack_orm.ContextBlock(
                    element=slack_orm.ContextElement(
                        initial_value="Opens in a new window",
                    ),
                    action="context",
                ),
            ]
        else:
            title_text = "Choose Activity"
            user_record = user_records[0]
            strava_recent_activities = strava.get_strava_activities(user_record)

            button_elements = []
            for activity in strava_recent_activities:
                date = datetime.strptime(activity["start_date_local"], "%Y-%m-%dT%H:%M:%SZ")
                date_fmt = date.strftime("%m-%d %H:%M")
                button_elements.append(
                    slack_orm.ButtonElement(
                        label=f"{date_fmt} - {activity['name']}",
                        action="-".join([actions.STRAVA_ACTIVITY_BUTTON, str(activity["id"])]),
                        value="|".join(
                            [
                                str(activity["id"]),
                                channel_id,
                                backblast_ts,
                                backblast_meta["title"],
                                moleskine_text[:2000],
                            ]
                        ),
                        # TODO: add confirmation modal
                    )
                )
                strava_blocks = [slack_orm.ActionsBlock(elements=button_elements)]

        strava_form = slack_orm.BlockView(blocks=strava_blocks)

        strava_form.post_modal(
            client=client,
            trigger_id=trigger_id,
            callback_id=actions.STRAVA_CALLBACK_ID,
            title_text=title_text,
            submit_button_text="None",
        )
    else:
        client.chat_postEphemeral(
            text="Connecting Strava to this Slackblast is only allowed for the tagged PAX."
            "Please contact one of them to make changes.",
            channel=channel_id,
            user=user_id,
        )


def build_strava_modify_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    strava_activity_id, channel_id, backblast_ts, backblast_title, backblast_moleskine = body["actions"][0][
        "value"
    ].split("|")
    view_id = safe_get(body, "container", "view_id")
    backblast_metadata = {
        "strava_activity_id": strava_activity_id,
        "channel_id": channel_id,
        "backblast_ts": backblast_ts,
    }

    modify_form = copy.deepcopy(forms.STRAVA_ACTIVITY_MODIFY_FORM)
    modify_form.set_initial_values(
        {
            actions.STRAVA_ACTIVITY_TITLE: backblast_title,
            actions.STRAVA_ACTIVITY_DESCRIPTION: f"{backblast_moleskine.replace('*','')}\n\nLearn more about F3 at https://f3nation.com",
        }
    )

    modify_form.update_modal(
        client=client,
        view_id=view_id,
        title_text="Modify Strava Activity",
        callback_id=actions.STRAVA_MODIFY_CALLBACK_ID,
        parent_metadata=backblast_metadata,
        submit_button_text="Modify Strava activity",
        close_button_text="Close without modifying",
        notify_on_close=True,
    )


def build_custom_field_menu(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region, update_view_id: str = None
) -> None:
    """Iterates through the custom fields and builds a menu to enable/disable and add/edit/delete them.

    Args:
        client (WebClient): Slack webclient
        region_record (Region): Region record
        trigger_id (str): The event's trigger id
        callback_id (str): The event's callback id
    """
    trigger_id = safe_get(body, "trigger_id")
    if safe_get(body, "actions", 0, "action_id") == actions.CONFIG_CUSTOM_FIELDS:
        update_view_id = None
    else:
        update_view_id = safe_get(body, "view", "id") or safe_get(body, "container", "view_id")

    blocks = []
    custom_fields = region_record.custom_fields or {}
    if region_record.custom_fields is None:
        custom_fields = {
            "Event Type": {
                "name": "Event Type",
                "type": "Dropdown",
                "options": ["Bootcamp", "QSource", "Rucking", "2nd F"],
                "enabled": False,
            }
        }
        DbManager.update_record(
            cls=Region,
            id=region_record.team_id,
            fields={"custom_fields": custom_fields},
        )

    for custom_field in custom_fields.values():
        label = f"Name: {custom_field['name']}\nType: {custom_field['type']}"
        if custom_field["type"] == "Dropdown":
            label += f"\nOptions: {', '.join(custom_field['options'])}"

        blocks.extend(
            [
                slack_orm.InputBlock(
                    element=slack_orm.RadioButtonsElement(
                        options=slack_orm.as_selector_options(
                            names=["Enabled", "Disabled"],
                            values=["enable", "disable"],
                        ),
                        initial_value="enable" if custom_field["enabled"] else "disable",
                    ),
                    action=f"{actions.CUSTOM_FIELD_ENABLE}_{custom_field['name']}",
                    label=label,
                    optional=False,
                ),
                slack_orm.ActionsBlock(
                    elements=[
                        slack_orm.ButtonElement(
                            label="Edit field",
                            action=actions.CUSTOM_FIELD_EDIT,
                            value=custom_field["name"],
                        ),
                        slack_orm.ButtonElement(
                            label="Delete field",
                            action=actions.CUSTOM_FIELD_DELETE,
                            value=custom_field["name"],
                        ),
                    ],
                ),
                slack_orm.DividerBlock(),
            ]
        )

    blocks.append(
        slack_orm.ActionsBlock(
            elements=[
                slack_orm.ButtonElement(
                    label="New custom field",
                    action=actions.CUSTOM_FIELD_ADD,
                ),
            ],
        )
    )
    view = slack_orm.BlockView(blocks=blocks)
    if update_view_id:
        view.update_modal(
            client=client,
            view_id=update_view_id,
            callback_id=actions.CUSTOM_FIELD_MENU_CALLBACK_ID,
            title_text="Custom Slackblast fields",
        )
    else:
        view.post_modal(
            client=client,
            trigger_id=trigger_id,
            callback_id=actions.CUSTOM_FIELD_MENU_CALLBACK_ID,
            title_text="Custom Slackblast fields",
            new_or_add="add",
        )


def build_custom_field_add_edit(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region
) -> None:
    """Builds a form to add or edit a custom field.

    Args:
        client (WebClient): Slack webclient
        region_record (Region): Region record
        trigger_id (str): The event's trigger id
        callback_id (str): The event's callback id
        custom_field_name (str): The name of the custom field to edit
    """
    trigger_id = safe_get(body, "trigger_id")
    if safe_get(body, "actions", 0, "action_id") == actions.CUSTOM_FIELD_EDIT:
        custom_field_name = safe_get(body, "actions", 0, "value")
    else:
        custom_field_name = None

    custom_field_form = copy.deepcopy(forms.CUSTOM_FIELD_ADD_EDIT_FORM)
    custom_field = safe_get(region_record.custom_fields, custom_field_name or "")

    if custom_field:
        custom_field_form.set_initial_values(
            {
                actions.CUSTOM_FIELD_ADD_NAME: custom_field["name"],
                actions.CUSTOM_FIELD_ADD_TYPE: custom_field["type"],
                actions.CUSTOM_FIELD_ADD_OPTIONS: ",".join(custom_field["options"])
                if custom_field["type"] == "Dropdown"
                else " ",
            }
        )
        action_text = "Edit"
    else:
        action_text = "Add"

    custom_field_form.post_modal(
        client=client,
        trigger_id=trigger_id,
        callback_id=actions.CUSTOM_FIELD_ADD_CALLBACK_ID,
        title_text=f"{action_text} custom field",
        submit_button_text=f"{action_text} field",
        notify_on_close=True,
        new_or_add="add",
    )


def handle_custom_field_delete(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: Region,
    trigger_id: str,
):
    custom_fields: dict = region_record.custom_fields or {}
    custom_fields.pop(safe_get(body, "actions", 0, "value"))
    build_custom_field_menu(
        body=body,
        client=client,
        logger=logger,
        context=context,
        region_record=region_record,
        trigger_id=trigger_id,
    )


def handle_backblast_edit_button(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")

    backblast_data = json.loads(safe_get(body, "actions", 0, "value") or "{}")

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
        build_backblast_form(
            body=body,
            client=client,
            logger=logger,
            context=context,
            region_record=region_record,
        )
    else:
        client.chat_postEphemeral(
            text="Editing this backblast is only allowed for the Q(s), the original poster, or your local Slack admins."
            "Please contact one of them to make changes.",
            channel=channel_id,
            user=user_id,
        )


def delete_custom_field(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    custom_field_name = safe_get(body, "actions", 0, "value")
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    view_id = safe_get(body, "container", "view_id")

    custom_fields: dict = region_record.custom_fields
    custom_fields.pop(custom_field_name)
    DbManager.update_record(cls=Region, id=team_id, fields={"custom_fields": custom_fields})
    build_custom_field_menu(body, client, logger, context, region_record, update_view_id=view_id)


def handle_preblast_edit_button(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")

    preblast_data = json.loads(safe_get(body, "actions", 0, "value") or "{}")

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
