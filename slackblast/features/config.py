import copy
import json
import os
from logging import Logger

from cryptography.fernet import Fernet
from slack_sdk.web import WebClient

from utilities import constants
from utilities.database import DbManager
from utilities.database.orm import (
    Region,
)
from utilities.helper_functions import (
    safe_get,
    update_local_region_records,
)
from utilities.slack import actions, forms


def build_config_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    if safe_get(body, "command") == "/config-slackblast":
        initial_config_data = None
        update_view_id = safe_get(body, actions.LOADING_ID)
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
                actions.CONFIG_BACKBLAST_MOLESKINE_TEMPLATE: region_record.backblast_moleskin_template
                or constants.DEFAULT_BACKBLAST_MOLESKINE_TEMPLATE,
                actions.CONFIG_PREBLAST_MOLESKINE_TEMPLATE: region_record.preblast_moleskin_template
                or constants.DEFAULT_PREBLAST_MOLESKINE_TEMPLATE,
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

    config_form.update_modal(
        client=client,
        view_id=update_view_id,
        callback_id=actions.CONFIG_CALLBACK_ID,
        title_text="Configure Slackblast",
    )

def handle_config_post(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    config_data = forms.CONFIG_FORM.get_selected_values(body)

    fields = {
        # Region.paxminer_schema: paxminer_db,
        Region.email_enabled: 1 if safe_get(config_data, actions.CONFIG_EMAIL_ENABLE) == "enable" else 0,
        Region.editing_locked: 1 if safe_get(config_data, actions.CONFIG_EDITING_LOCKED) == "yes" else 0,
        Region.default_destination: safe_get(config_data, actions.CONFIG_DEFAULT_DESTINATION),
        Region.backblast_moleskin_template: safe_get(config_data, actions.CONFIG_BACKBLAST_MOLESKINE_TEMPLATE),
        Region.preblast_moleskin_template: safe_get(config_data, actions.CONFIG_PREBLAST_MOLESKINE_TEMPLATE),
        Region.strava_enabled: 1 if safe_get(config_data, actions.CONFIG_ENABLE_STRAVA) == "enable" else 0,
    }
    if safe_get(config_data, actions.CONFIG_EMAIL_ENABLE) == "enable":
        fernet = Fernet(os.environ[constants.PASSWORD_ENCRYPT_KEY].encode())
        email_password_decrypted = safe_get(config_data, actions.CONFIG_EMAIL_PASSWORD)
        if email_password_decrypted:
            email_password_encrypted = fernet.encrypt(
                safe_get(config_data, actions.CONFIG_EMAIL_PASSWORD).encode()
            ).decode()
        else:
            email_password_encrypted = None
        fields.update(
            {
                Region.email_option_show: 1 if safe_get(config_data, actions.CONFIG_EMAIL_SHOW_OPTION) == "yes" else 0,
                Region.email_server: safe_get(config_data, actions.CONFIG_EMAIL_SERVER),
                Region.email_server_port: safe_get(config_data, actions.CONFIG_EMAIL_PORT),
                Region.email_user: safe_get(config_data, actions.CONFIG_EMAIL_FROM),
                Region.email_to: safe_get(config_data, actions.CONFIG_EMAIL_TO),
                Region.email_password: email_password_encrypted,
                Region.postie_format: 1 if safe_get(config_data, actions.CONFIG_POSTIE_ENABLE) == "yes" else 0,
            }
        )

    DbManager.update_record(
        cls=Region,
        id=context["team_id"],
        fields=fields,
    )
    update_local_region_records()
    print(json.dumps({"event_type": "successful_config_update", "team_name": region_record.workspace_name}))
