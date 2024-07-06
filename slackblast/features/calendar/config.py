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
        orm.ActionsBlock(
            elements=[
                orm.ButtonElement(
                    label=":gear: General Calendar Settings",
                    action=actions.CALENDAR_CONFIG_GENERAL,
                    value="edit",
                )
            ],
        ),
        orm.SectionBlock(
            label=":round_pushpin: Manage Locations",
            action=actions.CALENDAR_MANAGE_LOCATIONS,
            element=orm.OverflowElement(
                options=orm.as_selector_options(
                    names=["Add Location", "Edit or Deactivate Locations"],
                    values=["add", "edit"],
                ),
            ),
        ),
        orm.SectionBlock(
            label=":world_map: Manage AOs",
            action=actions.CALENDAR_MANAGE_AOS,
            element=orm.OverflowElement(
                options=orm.as_selector_options(
                    names=["Add AO", "Edit or Deactivate AOs"],
                    values=["add", "edit"],
                ),
            ),
        ),
        orm.SectionBlock(
            label=":spiral_calendar_pad: Manage Series",
            action=actions.CALENDAR_MANAGE_SERIES,
            element=orm.OverflowElement(
                options=orm.as_selector_options(
                    names=["Add Series", "Edit or Deactivate Series"],
                    values=["add", "edit"],
                ),
            ),
        ),
        orm.SectionBlock(
            label=":date: Manage Single Events",
            action=actions.CALENDAR_MANAGE_EVENTS,
            element=orm.OverflowElement(
                options=orm.as_selector_options(
                    names=["Add Single Event", "Edit or Deactivate Single Events"],
                    values=["add", "edit"],
                ),
            ),
        ),
        orm.SectionBlock(
            label=":runner: Manage Event Types",
            action=actions.CALENDAR_MANAGE_EVENT_TYPES,
            element=orm.OverflowElement(
                options=orm.as_selector_options(
                    names=["Add Event Type"],  # , "Edit or Deactivate Event Types"],
                    values=["add"],  # , "edit"],
                ),
            ),
        ),
        orm.SectionBlock(
            label=":label: Manage Event Tags",
            action=actions.CALENDAR_MANAGE_EVENT_TAGS,
            element=orm.OverflowElement(
                options=orm.as_selector_options(
                    names=["Add Event Tag", "Edit or Delete Event Tags"],
                    values=["add", "edit"],
                ),
            ),
        ),
    ]
)
