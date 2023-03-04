import json
from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from utilities.helper_functions import (
    get_oauth_flow,
    handle_backblast_post,
    safe_get,
    handle_preblast_post,
    handle_config_post,
    handle_backblast_edit_post,
    run_fuzzy_match,
)
from utilities import constants
from utilities.slack import forms
from utilities.slack import orm as slack_orm, actions
import logging
from datetime import datetime
from utilities.database import DbManager
from utilities.database.orm import Region
import os
from cryptography.fernet import Fernet
import re

logger = logging.getLogger()
logger.setLevel(logging.INFO)

app = App(process_before_response=True, oauth_flow=get_oauth_flow())


def handler(event, context):
    slack_handler = SlackRequestHandler(app=app)
    return slack_handler.handle(event, context)


def respond_to_command(ack, body, logger, client, context, initial_backblast_data: dict = None):
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
        region_record: Region = DbManager.create_record(
            Region(team_id=team_id, bot_token=context["bot_token"], workspace_name=team_name)
        )

    if safe_get(body, "command") == "/config-slackblast" or region_record.paxminer_schema is None:
        config_form = forms.CONFIG_FORM
        # paxminer_region_records = DbManager.execute_sql_query('select schema_name from paxminer.regions')
        # regions_list = [r['schema_name'] for r in paxminer_region_records]
        # logger.info("regions_list is {}".format(regions_list))
        # regions_list = [p.region for p in paxminer_region_records]

        if region_record:
            if region_record.email_password:
                fernet = Fernet(os.environ[constants.PASSWORD_ENCRYPT_KEY].encode())
                email_password_decrypted = fernet.decrypt(
                    region_record.email_password.encode()
                ).decode()
            else:
                email_password_decrypted = "SamplePassword123!"
            # config_form.set_options({
            #     actions.CONFIG_PAXMINER_DB: slack_orm.as_selector_options(regions_list)
            # })
            if region_record.paxminer_schema is None:
                logger.info("running fuzzy match")
                schema_best_guesses = run_fuzzy_match(region_record.workspace_name)
                schema_best_guesses.append("Other (enter below)")
                config_form.set_options(
                    {actions.CONFIG_PAXMINER_DB: slack_orm.as_selector_options(schema_best_guesses)}
                )
            config_form.set_initial_values(
                {
                    actions.CONFIG_PAXMINER_DB: region_record.paxminer_schema,
                    actions.CONFIG_EMAIL_ENABLE: "enable"
                    if region_record.email_enabled == 1
                    else "disable",
                    actions.CONFIG_EMAIL_SHOW_OPTION: "yes"
                    if region_record.email_option_show == 1
                    else "no",
                    actions.CONFIG_EMAIL_FROM: region_record.email_user
                    or "example_sender@gmail.com",
                    actions.CONFIG_EMAIL_TO: region_record.email_to
                    or "example_destination@gmail.com",
                    actions.CONFIG_EMAIL_SERVER: region_record.email_server or "smtp.gmail.com",
                    actions.CONFIG_EMAIL_PORT: str(region_record.email_server_port) or "587",
                    actions.CONFIG_EMAIL_PASSWORD: email_password_decrypted,
                    actions.CONFIG_POSTIE_ENABLE: "yes"
                    if region_record.postie_format == 1
                    else "no",
                }
            )
        config_form.post_modal(
            client=client,
            trigger_id=trigger_id,
            callback_id=actions.CONFIG_CALLBACK_ID,
            title_text="Configure Slackblast",
        )

    elif (
        safe_get(body, "command") == "/slackblast"
        or safe_get(body, "command") == "/backblast"
        or initial_backblast_data
    ):
        backblast_form = forms.BACKBLAST_FORM

        if initial_backblast_data:
            backblast_form.set_initial_values(initial_backblast_data)
            backblast_metadata = (
                safe_get(body, "container", "channel_id")
                + "|"
                + safe_get(body, "container", "message_ts")
            )
            backblast_form.delete_block(actions.BACKBLAST_EMAIL_SEND)
            backblast_form.delete_block(actions.BACKBLAST_DESTINATION)
            callback_id = actions.BACKBLAST_EDIT_CALLBACK_ID
        else:
            backblast_form.set_options(
                {
                    actions.BACKBLAST_DESTINATION: slack_orm.as_selector_options(
                        names=["The AO Channel", "My DMs"], values=["The_AO", user_id]
                    )
                }
            )
            if not (region_record.email_enabled & region_record.email_option_show):
                backblast_form.delete_block(actions.BACKBLAST_EMAIL_SEND)
            backblast_form.set_initial_values(
                {
                    actions.BACKBLAST_Q: user_id,
                    actions.BACKBLAST_DATE: datetime.now().strftime("%Y-%m-%d"),
                    actions.BACKBLAST_DESTINATION: "The_AO",
                }
            )
            if channel_id:
                backblast_form.set_initial_values({actions.BACKBLAST_AO: channel_id})
            backblast_metadata = None
            callback_id = actions.BACKBLAST_CALLBACK_ID

        backblast_form.post_modal(
            client=client,
            trigger_id=trigger_id,
            callback_id=callback_id,
            title_text="Backblast",
            parent_metadata=backblast_metadata,
        )

    elif safe_get(body, "command") == "/preblast":
        preblast_form = forms.PREBLAST_FORM
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
def handle_backblast_edit(ack, body, client, logger, context):
    ack()
    logger.info("body is {}".format(body))
    logger.info("context is {}".format(context))
    backblast_data: dict = json.loads(body["actions"][0]["value"])
    logger.info("backblast_data is {}".format(backblast_data))

    respond_to_command(ack, body, logger, client, context, initial_backblast_data=backblast_data)


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
