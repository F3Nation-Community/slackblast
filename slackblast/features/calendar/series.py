import copy
import json
from datetime import datetime, timedelta
from logging import Logger

from slack_sdk.web import WebClient

from utilities import constants
from utilities.database import DbManager
from utilities.database.orm import (
    Event,
    EventTag,
    EventTag_x_Org,
    EventType,
    EventType_x_Org,
    Location,
    Org,
    SlackSettings,
)
from utilities.helper_functions import safe_convert, safe_get
from utilities.slack import actions, orm


def manage_series(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "add":
        build_series_add_form(body, client, logger, context, region_record)
    elif action == "edit":
        build_series_list_form(body, client, logger, context, region_record)


def build_series_add_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    edit_event: Event | None = None,
):
    parent_metadata = {"series_id": edit_event.id} if edit_event else {}
    if safe_get(body, "actions", 0, "action_id") in (actions.CALENDAR_MANAGE_SERIES, actions.CALENDAR_ADD_SERIES_AO):
        title_text = "Add a Series"
        form = copy.deepcopy(SERIES_FORM)
        parent_metadata.update({"is_series": "True"})
    else:
        title_text = "Add an Event"
        form = copy.deepcopy(EVENT_FORM)
        parent_metadata.update({"is_series": "False"})

    aos = DbManager.find_records(Org, [Org.parent_id == region_record.org_id, Org.is_active, Org.org_type_id == 1])
    locations = DbManager.find_records(Location, [Location.org_id == region_record.org_id, Location.is_active])
    event_types = DbManager.find_join_records2(
        EventType, EventType_x_Org, [EventType_x_Org.org_id == region_record.org_id]
    )
    event_types = [x[0] for x in event_types]
    event_tags = DbManager.find_join_records2(EventTag, EventTag_x_Org, [EventTag_x_Org.org_id == region_record.org_id])
    event_tags = [x[0] for x in event_tags]

    form.set_options(
        {
            actions.CALENDAR_ADD_SERIES_AO: orm.as_selector_options(
                names=[ao.name for ao in aos],
                values=[str(ao.id) for ao in aos],
            ),
            actions.CALENDAR_ADD_EVENT_AO: orm.as_selector_options(
                names=[ao.name for ao in aos],
                values=[str(ao.id) for ao in aos],
            ),
            actions.CALENDAR_ADD_SERIES_LOCATION: orm.as_selector_options(
                names=[location.name for location in locations],
                values=[str(location.id) for location in locations],
            ),
            actions.CALENDAR_ADD_SERIES_TYPE: orm.as_selector_options(
                names=[event_type.name for event_type in event_types],
                values=[str(event_type.id) for event_type in event_types],
            ),
            actions.CALENDAR_ADD_SERIES_TAG: orm.as_selector_options(
                names=[tag.name for tag in event_tags],
                values=[str(tag.id) for tag in event_tags],
            ),
        }
    )

    if edit_event:
        initial_values = {
            actions.CALENDAR_ADD_SERIES_NAME: edit_event.name,
            actions.CALENDAR_ADD_SERIES_DESCRIPTION: edit_event.description,
            actions.CALENDAR_ADD_SERIES_AO: str(edit_event.org_id),
            actions.CALENDAR_ADD_EVENT_AO: str(edit_event.org_id),
            actions.CALENDAR_ADD_SERIES_LOCATION: str(edit_event.location_id),
            actions.CALENDAR_ADD_SERIES_TYPE: str(edit_event.event_type_id),
            actions.CALENDAR_ADD_SERIES_START_DATE: safe_convert(
                edit_event.start_date, datetime.strftime, ["%Y-%m-%d"]
            ),
            actions.CALENDAR_ADD_SERIES_END_DATE: safe_convert(edit_event.end_date, datetime.strftime, ["%Y-%m-%d"]),
            actions.CALENDAR_ADD_SERIES_START_TIME: safe_convert(edit_event.start_time, datetime.strftime, ["%H:%M"]),
            actions.CALENDAR_ADD_SERIES_END_TIME: safe_convert(edit_event.end_time, datetime.strftime, ["%H:%M"]),
            actions.CALENDAR_ADD_SERIES_DOW: [str(edit_event.day_of_week)],
            actions.CALENDAR_ADD_SERIES_FREQUENCY: edit_event.recurrence_pattern,
            actions.CALENDAR_ADD_SERIES_INTERVAL: edit_event.recurrence_interval,
            actions.CALENDAR_ADD_SERIES_INDEX: edit_event.index_within_interval,
        }
        if edit_event.event_tag_id:
            initial_values[actions.CALENDAR_ADD_SERIES_TAG] = str(edit_event.event_tag_id)
    else:
        initial_values = {
            actions.CALENDAR_ADD_SERIES_START_DATE: datetime.now().strftime("%Y-%m-%d"),
            actions.CALENDAR_ADD_SERIES_FREQUENCY: constants.FREQUENCY_OPTIONS[0],
            actions.CALENDAR_ADD_SERIES_INTERVAL: 1,
            actions.CALENDAR_ADD_SERIES_INDEX: 1,
        }

    # This is triggered when the AO is selected, defaults are loaded for the location and event type
    # TODO: is there a better way to update the modal without having to rebuild everything?
    action_id = safe_get(body, "actions", 0, "action_id")
    if action_id in (actions.CALENDAR_ADD_SERIES_AO, actions.CALENDAR_ADD_EVENT_AO):
        if action_id == actions.CALENDAR_ADD_SERIES_AO:
            form_data = SERIES_FORM.get_selected_values(body)
        else:
            form_data = EVENT_FORM.get_selected_values(body)
        ao: Org = DbManager.get_record(Org, safe_convert(safe_get(form_data, action_id), int))
        default_event_type = DbManager.find_records(
            EventType_x_Org,
            [EventType_x_Org.org_id == safe_get(form_data, action_id), EventType_x_Org.is_default],
        )
        if ao:
            if ao.default_location_id:
                initial_values[actions.CALENDAR_ADD_SERIES_LOCATION] = str(ao.default_location_id)
        if default_event_type:
            initial_values[actions.CALENDAR_ADD_SERIES_TYPE] = str(default_event_type[0].event_type_id)

        form.set_initial_values(initial_values)
        form.update_modal(
            client=client,
            view_id=safe_get(body, "view", "id"),
            callback_id=actions.ADD_SERIES_CALLBACK_ID,
            title_text=title_text,
            parent_metadata=parent_metadata,
        )
    else:
        form.set_initial_values(initial_values)
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text=title_text,
            callback_id=actions.ADD_SERIES_CALLBACK_ID,
            new_or_add="add",
            parent_metadata=parent_metadata,
        )


def handle_series_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    metadata = safe_convert(safe_get(body, "view", "private_metadata"), json.loads)
    if metadata.get("is_series") == "False":
        form_data = EVENT_FORM.get_selected_values(body)
    else:
        form_data = SERIES_FORM.get_selected_values(body)

    end_date = safe_convert(safe_get(form_data, actions.CALENDAR_ADD_SERIES_END_DATE), datetime.strptime, ["%Y-%m-%d"])

    if safe_get(form_data, actions.CALENDAR_ADD_SERIES_END_TIME):
        end_time = datetime.strptime(safe_get(form_data, actions.CALENDAR_ADD_SERIES_END_TIME), "%H:%M")
    else:
        end_time = datetime.strptime(safe_get(form_data, actions.CALENDAR_ADD_SERIES_START_TIME), "%H:%M") + timedelta(
            hours=1
        )

    # Slack won't return the selection for location and event type after being defaulted, so we need to get the initial value # noqa
    view_blocks = safe_get(body, "view", "blocks")
    location_block = [block for block in view_blocks if block["block_id"] == actions.CALENDAR_ADD_SERIES_LOCATION][0]
    location_initial_value = safe_get(location_block, "element", "initial_option", "value")
    location_id = form_data.get(actions.CALENDAR_ADD_SERIES_LOCATION) or location_initial_value
    event_type_block = [block for block in view_blocks if block["block_id"] == actions.CALENDAR_ADD_SERIES_TYPE][0]
    event_type_initial_value = safe_get(event_type_block, "element", "initial_option", "value")
    event_type_id = form_data.get(actions.CALENDAR_ADD_SERIES_TYPE) or event_type_initial_value

    # Apply int conversion to all values if not null
    location_id = safe_convert(location_id, int)
    event_type_id = safe_convert(event_type_id, int)
    org_id = safe_convert(
        safe_get(form_data, actions.CALENDAR_ADD_SERIES_AO) or safe_get(form_data, actions.CALENDAR_ADD_EVENT_AO), int
    )
    event_tag_id = safe_convert(safe_get(form_data, actions.CALENDAR_ADD_SERIES_TAG), int)
    recurrence_interval = safe_convert(safe_get(form_data, actions.CALENDAR_ADD_SERIES_INTERVAL), int)
    index_within_interval = safe_convert(safe_get(form_data, actions.CALENDAR_ADD_SERIES_INDEX), int)

    if safe_get(form_data, actions.CALENDAR_ADD_SERIES_NAME):
        series_name = safe_get(form_data, actions.CALENDAR_ADD_SERIES_NAME)
    else:
        org = DbManager.get_record(Org, org_id)
        event_type = DbManager.get_record(EventType, event_type_id)
        series_name = f"{org.name} {event_type.name if event_type else ''}"

    series_records = []
    day_of_weeks = safe_get(form_data, actions.CALENDAR_ADD_SERIES_DOW)

    if safe_get(metadata, "series_id"):
        edit_series_record = DbManager.get_record(Event, metadata["series_id"])
        day_of_weeks = [str(edit_series_record.day_of_week)]

    # day_of_weeks will be None if this is a one-time event
    if not day_of_weeks:
        series_records = [
            Event(
                name=series_name,
                org_id=org_id,
                location_id=location_id,
                event_type_id=event_type_id,
                event_tag_id=event_tag_id,
                start_date=datetime.strptime(safe_get(form_data, actions.CALENDAR_ADD_SERIES_START_DATE), "%Y-%m-%d"),
                start_time=datetime.strptime(safe_get(form_data, actions.CALENDAR_ADD_SERIES_START_TIME), "%H:%M"),
                end_time=end_time,
                is_series=False,
                is_active=True,
                highlight=safe_get(form_data, actions.CALENDAR_ADD_SERIES_HIGHLIGHT) == ["True"],
            )
        ]
    else:
        for dow in day_of_weeks:
            series = Event(
                name=series_name,
                description=safe_get(form_data, actions.CALENDAR_ADD_SERIES_DESCRIPTION),
                org_id=org_id,
                location_id=location_id,
                event_type_id=event_type_id,
                event_tag_id=event_tag_id,
                start_date=datetime.strptime(safe_get(form_data, actions.CALENDAR_ADD_SERIES_START_DATE), "%Y-%m-%d"),
                end_date=end_date,
                start_time=datetime.strptime(safe_get(form_data, actions.CALENDAR_ADD_SERIES_START_TIME), "%H:%M"),
                end_time=end_time,
                recurrence_pattern=safe_get(form_data, actions.CALENDAR_ADD_SERIES_FREQUENCY)
                or edit_series_record.recurrence_pattern,
                recurrence_interval=recurrence_interval or edit_series_record.recurrence_interval,
                index_within_interval=index_within_interval or edit_series_record.index_within_interval,
                day_of_week=int(dow) if dow else edit_series_record.day_of_week,
                is_series=True,
                is_active=True,
                highlight=safe_get(form_data, actions.CALENDAR_ADD_SERIES_HIGHLIGHT) == ["True"],
            )
            series_records.append(series)

    if safe_get(metadata, "series_id"):
        # series_id is passed in the metadata if this is an edit
        update_dict = series_records[0].__dict__
        update_dict.pop("_sa_instance_state")
        DbManager.update_record(Event, metadata["series_id"], fields=update_dict)
        records = [Event(id=metadata["series_id"], **update_dict)]

        # Delete all future events associated with the series
        # TODO: I could do a check to see if dates / times have changed, if not we could update the events instead of deleting them # noqa
        DbManager.delete_records(
            Event,
            [
                Event.series_id == metadata["series_id"],
                Event.start_date >= datetime.now(),
            ],
        )
    else:
        records = DbManager.create_records(series_records)

    # Now that the series has been created, we need to create the individual events
    if day_of_weeks:
        create_events(records)

    if safe_get(metadata, "series_id"):
        body["actions"] = [{"action_id": actions.CALENDAR_MANAGE_SERIES}]
        build_series_list_form(
            body, client, logger, context, region_record, update_view_id=safe_get(body, "view", "previous_view_id")
        )


def create_events(records: list[Event]):
    event_records = []
    for series in records:
        current_date = series.start_date
        end_date = series.end_date or series.start_date.replace(year=series.start_date.year + 1)
        max_interval = series.recurrence_interval or 1
        current_interval = 1
        current_index = 0

        # for monthly series, figure out which occurence of the day of the week the start date is within the month
        if series.recurrence_pattern == "Monthly":
            current_date = current_date.replace(day=1)
            while current_date <= series.start_date:
                if current_date.isoweekday() == series.day_of_week:
                    current_index += 1
                current_date += timedelta(days=1)

        # event creation algorithm
        while current_date <= end_date:
            if current_date.isoweekday() == series.day_of_week:
                current_index += 1
                if (current_index == series.index_within_interval) or (series.recurrence_pattern == "Weekly"):
                    if current_interval == 1:
                        event = Event(
                            name=series.name,
                            description=series.description,
                            org_id=series.org_id,
                            location_id=series.location_id,
                            event_type_id=series.event_type_id,
                            event_tag_id=series.event_tag_id,
                            start_date=current_date,
                            end_date=current_date,
                            start_time=series.start_time,
                            end_time=series.end_time,
                            is_series=False,
                            is_active=True,
                            series_id=series.id,
                            highlight=series.highlight,
                        )
                        event_records.append(event)
                    current_interval = current_interval + 1 if current_interval < max_interval else 1
            current_date += timedelta(days=1)
            if current_date.day == 1:
                current_index = 0
    DbManager.create_records(event_records)


def build_series_list_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    update_view_id=None,
):
    if safe_get(body, "actions", 0, "action_id") == actions.CALENDAR_MANAGE_SERIES:
        is_series = True
        title_text = "Delete or Edit a Series"
        confirm_text = "Are you sure you want to edit / delete this series? This cannot be undone. Also, editing or deleting a series will also edit or delete all future events associated with the series."  # noqa
    else:
        is_series = False
        title_text = "Delete or Edit an Event"
        confirm_text = "Are you sure you want to edit / delete this event? This cannot be undone."

    series_records = DbManager.find_join_records2(
        Event,
        Org,
        [
            Event.is_series == is_series,
            (Event.org_id == region_record.org_id) or (Org.parent_id == region_record.org_id),
            Event.is_active,
            # Event.start_date >= datetime.now(),
        ],
    )
    series_records = [x[0] for x in series_records][:40]

    # TODO: separate into weekly / non-weekly series?
    # TODO: add an AO filter
    blocks = []
    for s in series_records:
        if is_series:
            label = f"{s.name} ({constants.DAY_OF_WEEK_OPTIONS['names'][s.day_of_week-1]} @ {datetime.strftime(s.start_time), '%H%M'})"[  # noqa
                :50
            ]
        else:
            label = f"{s.name} ({s.start_date.strftime('%m/%d/%Y')})"[:50]

        blocks.append(
            orm.SectionBlock(
                label=label,
                action=f"{actions.SERIES_EDIT_DELETE}_{s.id}",
                element=orm.StaticSelectElement(
                    placeholder="Edit or Delete",
                    options=orm.as_selector_options(names=["Edit", "Delete"]),
                    confirm=orm.ConfirmObject(
                        title="Are you sure?",
                        text=confirm_text,
                        confirm="Yes, I'm sure",
                        deny="Whups, never mind",
                    ),
                ),
            )
        )
    form = orm.BlockView(blocks=blocks)
    if update_view_id:
        form.update_modal(
            client=client,
            view_id=update_view_id,
            callback_id=actions.EDIT_DELETE_SERIES_CALLBACK_ID,
            title_text=title_text,
            submit_button_text="None",
        )
    else:
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            title_text=title_text,
            callback_id=actions.EDIT_DELETE_SERIES_CALLBACK_ID,
            submit_button_text="None",
            new_or_add="add",
            parent_metadata={"is_series": str(is_series)},
        )


def handle_series_edit_delete(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    series_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[1], int)
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "Edit":
        series = DbManager.get_record(Event, series_id)
        build_series_add_form(body, client, logger, context, region_record, edit_event=series)
    elif action == "Delete":
        DbManager.update_record(Event, series_id, fields={"is_active": False})
        DbManager.update_records(
            Event, [Event.series_id == series_id, Event.start_date >= datetime.now()], fields={"is_active": False}
        )
        build_series_list_form(
            body, client, logger, context, region_record, update_view_id=safe_get(body, "view", "id")
        )


SERIES_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Series Name",
            action=actions.CALENDAR_ADD_SERIES_NAME,
            element=orm.PlainTextInputElement(placeholder="Enter the series name"),
            hint="If left blank, will default to the AO name + event type.",
        ),
        orm.InputBlock(
            label="Description",
            action=actions.CALENDAR_ADD_SERIES_DESCRIPTION,
            element=orm.PlainTextInputElement(
                placeholder="Enter a description",
                multiline=True,
            ),
            optional=True,
        ),
        orm.InputBlock(
            label="Highlight on Special Events Page?",
            action=actions.CALENDAR_ADD_SERIES_HIGHLIGHT,
            element=orm.CheckboxInputElement(
                options=orm.as_selector_options(names=["Yes"], values=["True"]),
            ),
            hint="Primarily used for 2nd F events, convergences, etc.",
        ),
        orm.InputBlock(
            label="AO",
            action=actions.CALENDAR_ADD_SERIES_AO,
            element=orm.StaticSelectElement(placeholder="Select an AO"),
            dispatch_action=True,
        ),
        orm.InputBlock(
            label="Default Location",
            action=actions.CALENDAR_ADD_SERIES_LOCATION,
            element=orm.StaticSelectElement(placeholder="Select the default location"),
        ),
        orm.InputBlock(
            label="Default Event Type",
            action=actions.CALENDAR_ADD_SERIES_TYPE,
            element=orm.StaticSelectElement(placeholder="Select the event type"),
            optional=False,
        ),
        orm.InputBlock(
            label="Default Event Tag",
            action=actions.CALENDAR_ADD_SERIES_TAG,
            element=orm.StaticSelectElement(placeholder="Select the event tag"),
            optional=True,
        ),
        orm.InputBlock(
            label="Start Date",
            action=actions.CALENDAR_ADD_SERIES_START_DATE,
            element=orm.DatepickerElement(placeholder="Enter the start date"),
            optional=False,
        ),
        orm.InputBlock(
            label="End Date",
            action=actions.CALENDAR_ADD_SERIES_END_DATE,
            element=orm.DatepickerElement(placeholder="Enter the end date"),
            hint="If no end date is provided, the series will continue indefinitely.",
        ),
        orm.InputBlock(
            label="Start Time",
            action=actions.CALENDAR_ADD_SERIES_START_TIME,
            element=orm.TimepickerElement(placeholder="Enter the start time"),
            optional=False,
        ),
        orm.InputBlock(
            label="End Time",
            action=actions.CALENDAR_ADD_SERIES_END_TIME,
            element=orm.TimepickerElement(placeholder="Enter the end time"),
            hint="If no end time is provided, the event will be defaulted to be one hour long.",
        ),
        orm.InputBlock(
            label="Day(s) of the Week",
            action=actions.CALENDAR_ADD_SERIES_DOW,
            element=orm.CheckboxInputElement(
                options=orm.as_selector_options(
                    names=constants.DAY_OF_WEEK_OPTIONS["names"],
                    values=[str(v) for v in constants.DAY_OF_WEEK_OPTIONS["values"]],
                ),
            ),
            optional=False,
        ),
        orm.InputBlock(
            label="Series Frequency",
            action=actions.CALENDAR_ADD_SERIES_FREQUENCY,
            element=orm.StaticSelectElement(
                placeholder="Select the frequency",
                options=orm.as_selector_options(names=constants.FREQUENCY_OPTIONS),
            ),
        ),
        orm.InputBlock(
            label="Interval",
            action=actions.CALENDAR_ADD_SERIES_INTERVAL,
            element=orm.NumberInputElement(
                placeholder="Enter the interval",
                is_decimal_allowed=False,
            ),
            optional=True,
            hint="For example, Interval=2 and Frequency=Weekly would mean every other week. If left blank, the interval will assumed to be 1.",  # noqa
        ),
        orm.InputBlock(
            label="Index within the interval",
            action=actions.CALENDAR_ADD_SERIES_INDEX,
            element=orm.NumberInputElement(
                placeholder="Enter the index",
                is_decimal_allowed=False,
            ),
            optional=True,
            hint="For example, Index=2 and Frequency=Monthly would mean the second week of the month. If left blank, the index will assumed to be 1.",  # noqa
        ),
    ]
)

EVENT_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Event Name",
            action=actions.CALENDAR_ADD_SERIES_NAME,
            element=orm.PlainTextInputElement(placeholder="Enter the event name"),
            hint="If left blank, will default to the AO name + event type.",
        ),
        orm.InputBlock(
            label="Highlight on Special Events Page?",
            action=actions.CALENDAR_ADD_SERIES_HIGHLIGHT,
            element=orm.CheckboxInputElement(
                options=orm.as_selector_options(names=["Yes"], values=["True"]),
            ),
            hint="Primarily used for 2nd F events, convergences, etc.",
        ),
        orm.InputBlock(
            label="AO",
            action=actions.CALENDAR_ADD_EVENT_AO,
            element=orm.StaticSelectElement(placeholder="Select an AO"),
            dispatch_action=True,
        ),
        orm.InputBlock(
            label="Location",
            action=actions.CALENDAR_ADD_SERIES_LOCATION,
            element=orm.StaticSelectElement(placeholder="Select the location"),
        ),
        orm.InputBlock(
            label="Event Type",
            action=actions.CALENDAR_ADD_SERIES_TYPE,
            element=orm.StaticSelectElement(placeholder="Select the event type"),
            optional=False,
        ),
        orm.InputBlock(
            label="Event Tag",
            action=actions.CALENDAR_ADD_SERIES_TAG,
            element=orm.StaticSelectElement(placeholder="Select the event tag"),
            optional=True,
        ),
        orm.InputBlock(
            label="Date",
            action=actions.CALENDAR_ADD_SERIES_START_DATE,
            element=orm.DatepickerElement(placeholder="Enter the start date"),
            optional=False,
        ),
        orm.InputBlock(
            label="Start Time",
            action=actions.CALENDAR_ADD_SERIES_START_TIME,
            element=orm.TimepickerElement(placeholder="Enter the start time"),
            optional=False,
        ),
        orm.InputBlock(
            label="End Time",
            action=actions.CALENDAR_ADD_SERIES_END_TIME,
            element=orm.TimepickerElement(placeholder="Enter the end time"),
            hint="If no end time is provided, the event will be defaulted to be one hour long.",
        ),
    ]
)
