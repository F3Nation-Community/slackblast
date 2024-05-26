import copy
from logging import Logger

from slack_sdk.web import WebClient

from utilities.database.orm import Region
from utilities.helper_functions import safe_get
from utilities.slack import actions, orm


def build_calendar_config_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    form = copy.deepcopy(CALENDAR_CONFIG_FORM)
    form.update_modal(  # TODO: add a "back to main menu" button?
        client=client,
        view_id=safe_get(body, "view", "id"),
        title_text="Calendar Settings",
        callback_id=actions.CALENDAR_CONFIG_CALLBACK_ID,
        submit_button_text="None",
    )


CALENDAR_CONFIG_FORM = orm.BlockView(
    blocks=[
        orm.SectionBlock(label=":gear: General Calendar Settings"),
        orm.ActionsBlock(
            elements=[
                orm.ButtonElement(
                    label="Edit Calendar Settings",
                    action=actions.CALENDAR_CONFIG_GENERAL,
                    value="edit",
                )
            ],
        ),
        orm.SectionBlock(label=":round_pushpin: Manage Locations"),
        orm.ActionsBlock(
            elements=[
                orm.ButtonElement(
                    label="Add Location",
                    action=actions.CALENDAR_ADD_LOCATION,
                    value="add",
                ),
            ],
        ),
        orm.SectionBlock(label=":world_map: Manage AOs"),
        orm.ActionsBlock(
            elements=[
                orm.ButtonElement(
                    label="Add AO",
                    action=actions.CALENDAR_ADD_AO,
                    value="add",
                ),
                orm.ButtonElement(
                    label="Edit or Delete AOs",
                    action=actions.CALENDAR_EDIT_AO,
                    value="edit",
                ),
            ],
        ),
        orm.SectionBlock(label=":spiral_calendar_pad: Manage Series"),
        orm.ActionsBlock(
            elements=[
                orm.ButtonElement(
                    label="Add Series",
                    action=actions.CALENDAR_ADD_SERIES,
                    value="add",
                ),
                orm.ButtonElement(
                    label="Edit or Delete Series",
                    action=actions.CALENDAR_EDIT_SERIES,
                    value="edit",
                ),
            ],
        ),
        orm.SectionBlock(label=":date: Manage Single Events"),
        orm.ActionsBlock(
            elements=[
                orm.ButtonElement(
                    label="Add Single Event",
                    action=actions.CALENDAR_ADD_SINGLE_EVENT,
                    value="add",
                ),
                orm.ButtonElement(
                    label="Edit or Delete Single Events",
                    action=actions.CALENDAR_EDIT_SINGLE_EVENT,
                    value="edit",
                ),
            ],
        ),
    ]
)
