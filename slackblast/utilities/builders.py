import copy
from logging import Logger

from slack_sdk.web import WebClient

from utilities import constants
from utilities.database.orm import SlackSettings
from utilities.helper_functions import safe_get
from utilities.slack import actions, forms

# from pymysql.err import ProgrammingError


def add_loading_form(body: dict, client: WebClient) -> str:
    trigger_id = safe_get(body, "trigger_id")
    loading_form_response = forms.LOADING_FORM.post_modal(
        client=client,
        trigger_id=trigger_id,
        title_text="Loading...",
        submit_button_text="None",
        callback_id="loading-id",
    )
    return safe_get(loading_form_response, "view", "id")


def ignore_event(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    logger.debug("Ignoring event")


def send_error_response(body: dict, client: WebClient, error: str) -> None:
    error_form = copy.deepcopy(forms.ERROR_FORM)
    error_msg = constants.ERROR_FORM_MESSAGE_TEMPLATE.format(error=error)
    error_form.set_initial_values({actions.ERROR_FORM_MESSAGE: error_msg})

    if safe_get(body, actions.LOADING_ID):
        update_view_id = safe_get(body, actions.LOADING_ID)
        error_form.update_modal(
            client=client,
            view_id=update_view_id,
            title_text="Slackblast Error",
            submit_button_text="None",
            callback_id="error-id",
        )
    else:
        blocks = [block.as_form_field() for block in error_form.blocks]
        client.chat_postMessage(channel=safe_get(body, "user", "id"), text=error, blocks=blocks)
