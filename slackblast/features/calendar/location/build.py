import copy
from logging import Logger

from slack_sdk.web import WebClient

from features.calendar.location import ui
from utilities.database import DbManager
from utilities.database.orm import Location, Region
from utilities.helper_functions import safe_get
from utilities.slack import actions


def build_location_add_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    form = copy.deepcopy(ui.ADD_LOCATION_FORM)
    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Add a Location",
        callback_id=actions.ADD_LOCATION_CALLBACK_ID,
        new_or_add="add",
    )


def handle_location_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    form_data = ui.ADD_LOCATION_FORM.get_selected_values(body)

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
        lat=google_lat,
        long=google_long,
    )

    DbManager.create_record(location)
