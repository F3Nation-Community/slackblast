import copy
import json
from logging import Logger

from slack_sdk.web import WebClient

from features.calendar import ao
from utilities.database import DbManager
from utilities.database.orm import Location, Region
from utilities.helper_functions import safe_convert, safe_get
from utilities.slack import actions, orm


def manage_locations(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "add":
        build_location_add_form(body, client, logger, context, region_record)
    elif action == "edit":
        build_location_list_form(body, client, logger, context, region_record)


def build_location_add_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: Region,
    edit_location: Location = None,
):
    form = copy.deepcopy(LOCATION_FORM)
    action_id = safe_get(body, "actions", 0, "action_id")

    if edit_location:
        form.set_initial_values(
            {
                actions.CALENDAR_ADD_LOCATION_NAME: edit_location.name,
                actions.CALENDAR_ADD_LOCATION_DESCRIPTION: edit_location.description,
            }
        )
        if edit_location.lat and edit_location.lon:
            form.set_initial_values(
                {
                    actions.CALENDAR_ADD_LOCATION_GOOGLE: f"{edit_location.lat}, {edit_location.lon}",
                }
            )
        title_text = "Edit Location"
    else:
        title_text = "Add a Location"

    parent_metadata = (
        {"update_view_id": safe_get(body, "view", "id")} if action_id == actions.CALENDAR_ADD_AO_NEW_LOCATION else {}
    )
    parent_metadata = {}
    if action_id == actions.CALENDAR_ADD_AO_NEW_LOCATION:
        parent_metadata["update_view_id"] = safe_get(body, "view", "id")
        form_data = ao.AO_FORM.get_selected_values(body)
        parent_metadata.update(form_data)
    if edit_location:
        parent_metadata["location_id"] = edit_location.id

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text=title_text,
        callback_id=actions.ADD_LOCATION_CALLBACK_ID,
        new_or_add="add",
        parent_metadata=parent_metadata,
    )


def handle_location_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    form_data = LOCATION_FORM.get_selected_values(body)
    metadata = safe_convert(safe_get(body, "view", "private_metadata"), json.loads)

    google_lat_long = safe_get(form_data, actions.CALENDAR_ADD_LOCATION_GOOGLE)
    if google_lat_long:
        google_lat, google_long = google_lat_long.split(",")
        google_lat = google_lat.strip()
        google_long = google_long.strip()
    else:
        google_lat = None
        google_long = None

    location: Location = Location(
        name=safe_get(form_data, actions.CALENDAR_ADD_LOCATION_NAME),
        description=safe_get(form_data, actions.CALENDAR_ADD_LOCATION_DESCRIPTION),
        is_active=True,
        lat=google_lat,
        lon=google_long,
        org_id=region_record.org_id,
    )

    if safe_get(metadata, "location_id"):
        # location_id is passed in the metadata if this is an edit
        update_dict = location.__dict__
        update_dict.pop("_sa_instance_state")
        DbManager.update_record(Location, metadata["location_id"], fields=update_dict)
    else:
        location = DbManager.create_record(location)

    if safe_get(metadata, "update_view_id"):
        update_metadata = {
            actions.CALENDAR_ADD_AO_NAME: safe_get(metadata, actions.CALENDAR_ADD_AO_NAME),
            actions.CALENDAR_ADD_AO_DESCRIPTION: safe_get(metadata, actions.CALENDAR_ADD_AO_DESCRIPTION),
            actions.CALENDAR_ADD_AO_CHANNEL: safe_get(metadata, actions.CALENDAR_ADD_AO_CHANNEL),
            actions.CALENDAR_ADD_AO_LOCATION: str(location.id),
            actions.CALENDAR_ADD_AO_TYPE: safe_get(metadata, actions.CALENDAR_ADD_AO_TYPE),
        }
        ao.build_ao_add_form(
            body,
            client,
            logger,
            context,
            region_record,
            update_view_id=metadata["update_view_id"],
            update_metadata=update_metadata,
        )


def build_location_list_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    location_records = DbManager.find_records(Location, [Location.org_id == region_record.org_id])

    blocks = [
        orm.SectionBlock(
            label=s.name,
            action=f"{actions.LOCATION_EDIT_DELETE}_{s.id}",
            element=orm.StaticSelectElement(
                placeholder="Edit or Delete",
                options=orm.as_selector_options(names=["Edit", "Delete"]),
                confirm=orm.ConfirmObject(
                    title="Are you sure?",
                    text="Are you sure you want to edit / delete this location? This cannot be undone.",  # noqa
                    confirm="Yes, I'm sure",
                    deny="Whups, never mind",
                ),
            ),
        )
        for s in location_records
    ]

    # TODO: add a "next page" button if there are more than 50 locations

    form = orm.BlockView(blocks=blocks)
    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Edit/Delete a Location",
        callback_id=actions.EDIT_DELETE_LOCATION_CALLBACK_ID,
        submit_button_text="None",
        new_or_add="add",
    )


def handle_location_edit_delete(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    location_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[1], int)
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "Edit":
        location = DbManager.get_record(Location, location_id)
        build_location_add_form(body, client, logger, context, region_record, location)
    elif action == "Delete":
        DbManager.update_record(Location, location_id, fields={"is_active": False})


LOCATION_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Location Name",
            action=actions.CALENDAR_ADD_LOCATION_NAME,
            element=orm.PlainTextInputElement(placeholder="ie Central Park - Main Entrance"),
            optional=False,
        ),
        orm.ContextBlock(
            element=orm.ContextElement(
                initial_value="Use the actual name of the location, ie park name, etc. You will define the F3 AO name when you create AOs."  # noqa
            ),
        ),
        orm.InputBlock(
            label="Description / Address",
            action=actions.CALENDAR_ADD_LOCATION_DESCRIPTION,
            element=orm.PlainTextInputElement(
                placeholder="Enter a description and / or address",
                multiline=True,
            ),
        ),
        orm.InputBlock(
            label="Google Lat/Long",
            action=actions.CALENDAR_ADD_LOCATION_GOOGLE,
            element=orm.PlainTextInputElement(placeholder="ie '34.0522, -118.2437'"),
        ),
        orm.ContextBlock(
            element=orm.ContextElement(
                initial_value="To get Google's Lat/Long, long press to create a pin, then bring up the context menu and select the coordinates to copy them."  # noqa
            ),
        ),
    ]
)
