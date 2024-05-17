import copy
from logging import Logger

from slack_sdk.web import WebClient

from features.calendar.config import ui
from utilities.database.orm import Region
from utilities.helper_functions import safe_get
from utilities.slack import actions


def build_calendar_config_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    form = copy.deepcopy(ui.CALENDAR_CONFIG_FORM)
    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Calendar Settings",
        callback_id=actions.CALENDAR_CONFIG_CALLBACK_ID,
        submit_button_text="None",
        new_or_add="add",
    )
