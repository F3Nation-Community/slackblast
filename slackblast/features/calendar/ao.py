import copy
import datetime
import json
from logging import Logger

from slack_sdk.web import WebClient

from utilities.database import DbManager
from utilities.database.orm import Event, EventType, EventType_x_Org, Location, Location_x_Org, Org, Region
from utilities.helper_functions import safe_convert, safe_get
from utilities.slack import actions, orm


def build_ao_add_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: Region,
    edit_ao: Org = None,
):
    form = copy.deepcopy(AO_FORM)

    # Pull locations and event types for the region
    locations = DbManager.find_records(Location, [True])  # TODO: filter by region
    event_types = DbManager.find_records(EventType, [True])  # TODO: filter by region
    form.set_options(
        {
            actions.CALENDAR_ADD_AO_LOCATION: orm.as_selector_options(
                names=[location.name for location in locations],
                values=[str(location.id) for location in locations],
                # descriptions=[location.description for location in locations],
            ),
            actions.CALENDAR_ADD_AO_TYPE: orm.as_selector_options(
                names=[event_type.name for event_type in event_types],
                values=[str(event_type.id) for event_type in event_types],
                # descriptions=[event_type.description for event_type in event_types],
            ),
        }
    )

    if edit_ao:
        default_location = safe_get(
            DbManager.find_records(Location_x_Org, [Location_x_Org.org_id == edit_ao.id, Location_x_Org.is_default]), 0
        )
        default_event_type = safe_get(
            DbManager.find_records(EventType_x_Org, [EventType_x_Org.org_id == edit_ao.id, EventType_x_Org.is_default]),
            0,
        )
        form.set_initial_values(
            {
                actions.CALENDAR_ADD_AO_NAME: edit_ao.name,
                actions.CALENDAR_ADD_AO_DESCRIPTION: edit_ao.description,
                actions.CALENDAR_ADD_AO_CHANNEL: edit_ao.slack_id,
            }
        )
        if default_location:
            form.set_initial_values({actions.CALENDAR_ADD_AO_LOCATION: str(default_location.location_id)})
        if default_event_type:
            form.set_initial_values({actions.CALENDAR_ADD_AO_TYPE: str(default_event_type.event_type_id)})
        title_text = "Edit AO"
    else:
        title_text = "Add an AO"

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text=title_text,
        callback_id=actions.ADD_AO_CALLBACK_ID,
        new_or_add="add",
        parent_metadata={"ao_id": edit_ao.id} if edit_ao else {},
    )


def handle_ao_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    form_data = AO_FORM.get_selected_values(body)
    region_org_id = region_record.id  # TODO: make this truly from the org_id
    metatdata = safe_convert(safe_get(body, "view", "private_metadata"), json.loads)

    ao: Org = Org(
        parent_id=region_org_id,
        org_type_id=1,
        is_active=True,
        name=safe_get(form_data, actions.CALENDAR_ADD_AO_NAME),
        description=safe_get(form_data, actions.CALENDAR_ADD_AO_DESCRIPTION),
        slack_id=safe_get(form_data, actions.CALENDAR_ADD_AO_CHANNEL),
    )

    if safe_get(metatdata, "ao_id"):
        update_dict = ao.__dict__
        update_dict.pop("_sa_instance_state")
        DbManager.update_record(Org, metatdata["ao_id"], fields=update_dict)
    else:
        DbManager.create_record(ao)

    if safe_get(form_data, actions.CALENDAR_ADD_AO_LOCATION):
        location_x_org: Location_x_Org = Location_x_Org(
            location_id=safe_get(form_data, actions.CALENDAR_ADD_AO_LOCATION),
            org_id=metatdata["ao_id"] or ao.id,
            is_default=True,
        )
        DbManager.create_record(location_x_org)

    if safe_get(form_data, actions.CALENDAR_ADD_AO_TYPE):
        event_type_x_org: EventType_x_Org = EventType_x_Org(
            event_type_id=safe_get(form_data, actions.CALENDAR_ADD_AO_TYPE),
            org_id=metatdata["ao_id"] or ao.id,
            is_default=True,
        )
        DbManager.create_record(event_type_x_org)


def build_ao_list_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    ao_records = DbManager.find_records(Org, [Org.parent_id == region_record.id, Org.org_type_id == 1])

    blocks = [
        orm.SectionBlock(
            label=s.name,
            action=f"{actions.AO_EDIT_DELETE}_{s.id}",
            element=orm.StaticSelectElement(
                placeholder="Edit or Delete",
                options=orm.as_selector_options(names=["Edit", "Delete"]),
                confirm=orm.ConfirmObject(
                    title="Are you sure?",
                    text="Are you sure you want to edit / delete this AO? This cannot be undone. Deleting an AO will also delete all associated series and events.",  # noqa
                    confirm="Yes, I'm sure",
                    deny="Whups, never mind",
                ),
            ),
        )
        for s in ao_records
    ]

    form = orm.BlockView(blocks=blocks)
    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Edit or Delete an AO",
        callback_id=actions.EDIT_DELETE_AO_CALLBACK_ID,
        submit_button_text="None",
        new_or_add="add",
    )


def handle_ao_edit_delete(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    ao_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[1], int)
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "Edit":
        ao = DbManager.get_record(Org, ao_id)
        build_ao_add_form(body, client, logger, context, region_record, edit_ao=ao)
    elif action == "Delete":
        DbManager.update_record(Org, ao_id, fields={"is_active": False})
        DbManager.update_records(
            Event, [Event.org_id == ao_id, Event.start_date >= datetime.now()], fields={"is_active": False}
        )


AO_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="AO Title",
            action=actions.CALENDAR_ADD_AO_NAME,
            element=orm.PlainTextInputElement(placeholder="Enter the AO name"),
            optional=False,
        ),
        orm.InputBlock(
            label="Description",
            action=actions.CALENDAR_ADD_AO_DESCRIPTION,
            element=orm.PlainTextInputElement(placeholder="Enter a description for the AO", multiline=True),
        ),
        orm.InputBlock(
            label="Channel associated with this AO:",
            action=actions.CALENDAR_ADD_AO_CHANNEL,
            element=orm.ChannelsSelectElement(placeholder="Select a channel"),
        ),
        orm.InputBlock(
            label="Default Location",
            action=actions.CALENDAR_ADD_AO_LOCATION,
            element=orm.StaticSelectElement(placeholder="Select a location"),
        ),
        orm.InputBlock(
            label="Default Event Type",
            action=actions.CALENDAR_ADD_AO_TYPE,
            element=orm.StaticSelectElement(placeholder="Select an event type"),
        ),
        orm.ContextBlock(
            element=orm.ContextElement(
                initial_value="These options can be changed later for specific series or events."
            )
        ),  # noqa
    ]
)
