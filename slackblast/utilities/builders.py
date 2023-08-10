import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from slack_sdk.web import WebClient
from utilities.database.orm import Region
from utilities.slack import forms
from utilities.slack import orm as slack_orm, actions
from utilities import constants
from utilities.helper_functions import (
    get_channel_name,
    safe_get,
    run_fuzzy_match,
    check_for_duplicate,
)
import copy
from logging import Logger
from datetime import datetime, date
from cryptography.fernet import Fernet


def build_backblast_form(
    user_id: str,
    channel_id: str,
    channel_name: str,
    body: dict,
    client: WebClient,
    logger: Logger,
    region_record: Region,
    backblast_method: str,
    trigger_id: str = None,
    initial_backblast_data: dict = None,
    currently_duplicate: bool = False,
    update_view_id: str = None,
    duplicate_check: bool = False,
    parent_metadata: str = None,
):
    backblast_form = copy.deepcopy(forms.BACKBLAST_FORM)

    if backblast_method == "edit" or duplicate_check:
        parent_metadata_safe = parent_metadata or "|"
        og_ts = safe_get(body, "message", "ts") or parent_metadata_safe.split("|")[1]
        is_duplicate = check_for_duplicate(
            q=safe_get(initial_backblast_data, actions.BACKBLAST_Q),
            date=safe_get(initial_backblast_data, actions.BACKBLAST_DATE),
            ao=safe_get(initial_backblast_data, actions.BACKBLAST_AO),
            region_record=region_record,
            logger=logger,
            og_ts=og_ts,
        )
        ao_id = safe_get(initial_backblast_data, actions.BACKBLAST_AO)
        ao_name = get_channel_name(ao_id, logger, client)
    else:
        is_duplicate = check_for_duplicate(
            q=user_id,
            date=date.today(),
            ao=channel_id,
            region_record=region_record,
            logger=logger,
        )
        ao_id = channel_id
        ao_name = channel_name

    # if duplicate_check and currently_duplicate == is_duplicate:
    #     return

    if not is_duplicate:
        backblast_form.delete_block(actions.BACKBLAST_DUPLICATE_WARNING)

    if backblast_method == "edit" or duplicate_check:
        backblast_form.set_initial_values(initial_backblast_data)

    if backblast_method == "edit":
        backblast_metadata = parent_metadata or (
            safe_get(body, "container", "channel_id")
            + "|"
            + safe_get(body, "container", "message_ts")
        )
        backblast_form.delete_block(actions.BACKBLAST_EMAIL_SEND)
        backblast_form.delete_block(actions.BACKBLAST_DESTINATION)
        callback_id = actions.BACKBLAST_EDIT_CALLBACK_ID
    else:
        logger.info("ao_id is {}".format(ao_id))
        logger.info("channel_id is {}".format(channel_id))
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
        if region_record.default_destination or "" == constants.CONFIG_DESTINATION_CURRENT["value"]:
            default_destination_id = channel_id
        elif region_record.default_destination or "" == constants.CONFIG_DESTINATION_AO["value"]:
            default_destination_id = "The_AO"
        else:
            default_destination_id = None

        backblast_form.set_initial_values(
            {
                actions.BACKBLAST_Q: user_id,
                actions.BACKBLAST_DATE: datetime.now().strftime("%Y-%m-%d"),
                actions.BACKBLAST_DESTINATION: default_destination_id or "The_AO",
                actions.BACKBLAST_MOLESKIN: region_record.backblast_moleskin_template
                or constants.DEFAULT_BACKBLAST_MOLESKINE_TEMPLATE,
            }
        )
        if channel_id:
            backblast_form.set_initial_values({actions.BACKBLAST_AO: channel_id})

    logger.info("backblast_form is {}".format(backblast_form.as_form_field()))

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


def build_config_form(
    client: WebClient,
    trigger_id: str,
    region_record: Region,
    logger: Logger,
    initial_config_data: dict = None,
    update_view_id: str = None,
):
    config_form = copy.deepcopy(forms.CONFIG_FORM)

    if region_record:
        if region_record.email_password:
            fernet = Fernet(os.environ[constants.PASSWORD_ENCRYPT_KEY].encode())
            email_password_decrypted = fernet.decrypt(
                region_record.email_password.encode()
            ).decode()
        else:
            email_password_decrypted = "SamplePassword123!"

        # logger.info("running fuzzy match")
        # schema_best_guesses = run_fuzzy_match(region_record.workspace_name)
        # schema_best_guesses.append("Other (enter below)")
        # config_form.set_options(
        #     {actions.CONFIG_PAXMINER_DB: slack_orm.as_selector_options(schema_best_guesses)}
        # )

        config_form.set_initial_values(
            {
                # actions.CONFIG_PAXMINER_DB: region_record.paxminer_schema,
                actions.CONFIG_EMAIL_ENABLE: "enable"
                if region_record.email_enabled == 1
                else "disable",
                actions.CONFIG_EMAIL_SHOW_OPTION: "yes"
                if region_record.email_option_show == 1
                else "no",
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
            }
        )

    if not initial_config_data:
        email_enable = "enable" if region_record.email_enabled == 1 else "disable"
    else:
        email_enable = initial_config_data[actions.CONFIG_EMAIL_ENABLE]

    logger.info("email_enable is {}".format(email_enable))
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


def build_preblast_form(
    user_id: str,
    channel_id: str,
    client: WebClient,
    trigger_id: str,
    region_record: Region,
):
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
            actions.PREBLAST_MOLESKIN: region_record.preblast_moleskin_template or "",
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
