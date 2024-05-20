import copy
from logging import Logger

from slack_sdk.web import WebClient

from utilities.database import DbManager
from utilities.database.orm import EventType, EventType_x_Org, Location, Location_x_Org, Org, Region
from utilities.helper_functions import safe_get
from utilities.slack import actions, orm


def build_ao_add_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    form = copy.deepcopy(ADD_AO_FORM)

    locations = DbManager.find_records(Location, [True])  # TODO: filter by region
    event_types = DbManager.find_records(EventType, [True])  # TODO: filter by region
    form.set_options(
        {
            actions.CALENDAR_ADD_AO_LOCATION: orm.as_selector_options(
                names=[location.name for location in locations],
                values=[location.id for location in locations],
                # descriptions=[location.description for location in locations],
            ),
            actions.CALENDAR_ADD_AO_TYPE: orm.as_selector_options(
                names=[event_type.name for event_type in event_types],
                values=[event_type.id for event_type in event_types],
                # descriptions=[event_type.description for event_type in event_types],
            ),
        }
    )

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Add an AO",
        callback_id=actions.ADD_AO_CALLBACK_ID,
        new_or_add="add",
    )


def handle_ao_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    form_data = ADD_AO_FORM.get_selected_values(body)
    region_org_id = region_record.id  # TODO: make this truly from the org_id

    ao: Org = Org(
        parent_id=region_org_id,
        org_type_id=1,
        name=safe_get(form_data, actions.CALENDAR_ADD_AO_NAME),
        description=safe_get(form_data, actions.CALENDAR_ADD_AO_DESCRIPTION),
        slack_id=safe_get(form_data, actions.CALENDAR_ADD_AO_CHANNEL),
    )
    DbManager.create_record(ao)

    if safe_get(form_data, actions.CALENDAR_ADD_AO_LOCATION):
        location_x_org: Location_x_Org = Location_x_Org(
            location_id=safe_get(form_data, actions.CALENDAR_ADD_AO_LOCATION),
            org_id=ao.id,
            is_default=True,
        )
        DbManager.create_record(location_x_org)

    if safe_get(form_data, actions.CALENDAR_ADD_AO_TYPE):
        event_type_x_org: EventType_x_Org = EventType_x_Org(
            event_type_id=safe_get(form_data, actions.CALENDAR_ADD_AO_TYPE),
            org_id=ao.id,
            is_default=True,
        )
        DbManager.create_record(event_type_x_org)


ADD_AO_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="AO Title",
            element=orm.PlainTextInputElement(
                action_id=actions.CALENDAR_ADD_AO_NAME,
                placeholder="Enter the AO name",
            ),
            optional=False,
        ),
        orm.InputBlock(
            label="Description",
            element=orm.PlainTextInputElement(
                action_id=actions.CALENDAR_ADD_AO_DESCRIPTION,
                placeholder="Enter a description for the AO",
            ),
        ),
        orm.InputBlock(
            label="Channel associated with this AO:",
            element=orm.ChannelsSelectElement(
                action_id=actions.CALENDAR_ADD_AO_CHANNEL,
                placeholder="Select a channel",
            ),
        ),
        orm.InputBlock(
            label="Default Location",
            element=orm.StaticSelectElement(
                action_id=actions.CALENDAR_ADD_AO_LOCATION,
                placeholder="Select a location",
            ),
        ),
        orm.InputBlock(
            label="Default Event Type",
            element=orm.StaticSelectElement(
                action_id=actions.CALENDAR_ADD_AO_TYPE,
                placeholder="Select an event type",
            ),
        ),
        orm.ContextBlock(
            element=orm.ContextElement("These options can be changed later for specific series or events.")
        ),  # noqa
    ]
)
