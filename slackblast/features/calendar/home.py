import datetime
from logging import Logger

from slack_sdk.web import WebClient
from sqlalchemy import or_

from features.calendar.event_preblast import build_event_preblast_form
from utilities.database import DbManager
from utilities.database.orm import AttendanceNew, Event, EventType, EventType_x_Org, Org, Region
from utilities.database.special_queries import CalendarHomeQuery, home_schedule_query
from utilities.helper_functions import get_user_id, safe_convert, safe_get
from utilities.slack import actions, orm


def build_home_form(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region, update_view_id: str = None
):
    action_id = safe_get(body, "actions", 0, "action_id")
    if action_id == actions.CALENDAR_HOME_DATE_FILTER and not safe_get(body, "actions", 0, "selected_date"):
        return
    slack_user_id = safe_get(body, "user", "id") or safe_get(body, "user_id")
    user_id = get_user_id(slack_user_id, region_record, client, logger)

    ao_records = DbManager.find_records(Org, filters=[Org.parent_id == region_record.org_id])
    event_types = DbManager.find_join_records2(
        EventType, EventType_x_Org, [EventType_x_Org.org_id == region_record.org_id]
    )
    event_type_records = [x[0] for x in event_types]

    blocks = [
        orm.SectionBlock(label="*Upcoming Schedule*"),
        orm.InputBlock(
            label="Filter AOs",
            action=actions.CALENDAR_HOME_AO_FILTER,
            element=orm.MultiStaticSelectElement(
                placeholder="Filter AOs",
                options=orm.as_selector_options(
                    names=[ao.name for ao in ao_records],
                    values=[str(ao.id) for ao in ao_records],
                ),
            ),
            dispatch_action=True,
        ),
        orm.InputBlock(
            label="Filter Event Types",
            action=actions.CALENDAR_HOME_EVENT_TYPE_FILTER,
            element=orm.MultiStaticSelectElement(
                placeholder="Filter Event Types",
                options=orm.as_selector_options(
                    names=[event_type.name for event_type in event_type_records],
                    values=[str(event_type.id) for event_type in event_type_records],
                ),
            ),
            dispatch_action=True,
        ),
        orm.InputBlock(
            label="Start Search Date",
            action=actions.CALENDAR_HOME_DATE_FILTER,
            element=orm.DatepickerElement(
                placeholder="Start Search Date",
            ),
            dispatch_action=True,
        ),
        orm.InputBlock(
            label="Other options",
            action=actions.CALENDAR_HOME_Q_FILTER,
            element=orm.CheckboxInputElement(
                options=orm.as_selector_options(
                    names=["Show only open Q slots", "Show only my events", "Include events from nearby regions"],
                    values=[actions.FILTER_OPEN_Q, actions.FILTER_MY_EVENTS, actions.FILTER_NEARBY_REGIONS],
                ),
            ),
            dispatch_action=True,
        ),
        # orm.ActionsBlock(
        #     elements=[
        #         orm.StaticSelectElement(  # TODO: make these multi-selects?
        #             placeholder="Filter AOs",
        #             action=actions.CALENDAR_HOME_AO_FILTER,
        #             options=orm.as_selector_options(
        #                 names=[ao.name for ao in ao_records],
        #                 values=[str(ao.id) for ao in ao_records],
        #             ),
        #         ),
        #         orm.StaticSelectElement(  # TODO: make these multi-selects?
        #             placeholder="Filter Event Types",
        #             action=actions.CALENDAR_HOME_EVENT_TYPE_FILTER,
        #             options=orm.as_selector_options(
        #                 names=[event_type.name for event_type in event_type_records],
        #                 values=[str(event_type.id) for event_type in event_type_records],
        #             ),
        #         ),
        #         orm.DatepickerElement(
        #             action=actions.CALENDAR_HOME_DATE_FILTER,
        #             placeholder="Start Search Date",
        #         ),
        #         orm.CheckboxInputElement(
        #             action=actions.CALENDAR_HOME_Q_FILTER,
        #             options=orm.as_selector_options(names=["Show only open Q slots"], values=["yes"]),
        #         ),
        #     ],
        # ),
    ]

    if safe_get(body, "view"):
        existing_filter_data = orm.BlockView(blocks=blocks).get_selected_values(body)
    else:
        existing_filter_data = {}

    # Build the filter
    start_date = (
        safe_convert(
            safe_get(existing_filter_data, actions.CALENDAR_HOME_DATE_FILTER), datetime.datetime.strptime, ["%Y-%m-%d"]
        )
        or datetime.datetime.now()
    )

    if safe_get(existing_filter_data, actions.CALENDAR_HOME_AO_FILTER):
        filter_org_ids = [int(x) for x in safe_get(existing_filter_data, actions.CALENDAR_HOME_AO_FILTER)]
    else:
        filter_org_ids = [region_record.org_id]

    filter = [
        or_(Event.org_id.in_(filter_org_ids), Org.parent_id.in_(filter_org_ids)),
        ~Event.is_series,
        Event.start_date > start_date,
    ]

    if safe_get(existing_filter_data, actions.CALENDAR_HOME_EVENT_TYPE_FILTER):
        event_type_ids = [int(x) for x in safe_get(existing_filter_data, actions.CALENDAR_HOME_EVENT_TYPE_FILTER)]
        filter.append(Event.event_type_id.in_(event_type_ids))

    open_q_only = actions.FILTER_OPEN_Q in (safe_get(existing_filter_data, actions.CALENDAR_HOME_Q_FILTER) or [])
    # Run the query
    # TODO: implement pagination / dynamic limit
    events: list[CalendarHomeQuery] = home_schedule_query(user_id, filter, limit=5, open_q_only=open_q_only)

    if actions.FILTER_MY_EVENTS in (safe_get(existing_filter_data, actions.CALENDAR_HOME_Q_FILTER) or []):
        events = [x for x in events if x.user_attending]

    # Build the event list
    active_date = datetime.date(2020, 1, 1)
    block_count = 1
    for event in events:
        if block_count > 90:
            break
        if event.user_q:
            option_names = ["Edit Preblast"]
        else:
            option_names = ["View Preblast"]
        if event.event.start_date != active_date:
            active_date = event.event.start_date
            blocks.append(orm.SectionBlock(label=f":calendar: *{active_date.strftime('%A, %B %d')}*"))
            block_count += 1
        label = f"{event.event.name} @ {str(event.event.start_time).zfill(4)}"
        if event.planned_qs:
            label += f" / Q: {event.planned_qs}"
        else:
            label += " / Q: Open!"
            option_names.append("Take Q")
        if event.user_q:
            label += " :muscle:"
        if event.user_attending:
            label += " :white_check_mark:"
            option_names.append("Un-HC")
        else:
            option_names.append("HC")
        if event.event.preblast_rich:
            label += " :pencil:"
        blocks.append(
            orm.SectionBlock(
                label=label,
                element=orm.OverflowElement(
                    action=f"{actions.CALENDAR_HOME_EVENT}_{event.event.id}",
                    options=orm.as_selector_options(option_names),
                ),
            )
        )
        block_count += 1

    # TODO: add "next page" button
    form = orm.BlockView(blocks=blocks)
    form.set_initial_values(existing_filter_data)
    form.update_modal(
        client=client,
        view_id=update_view_id or safe_get(body, actions.LOADING_ID) or safe_get(body, "view", "id"),
        title_text="Calendar Home",
        callback_id=actions.CALENDAR_HOME_CALLBACK_ID,
        submit_button_text="None",
    )


def handle_home_event(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    event_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[1], int)
    action = safe_get(body, "actions", 0, "selected_option", "value")
    user_id = get_user_id(safe_get(body, "user", "id"), region_record, client, logger)
    view_id = safe_get(body, "view", "id")

    if action in ["View Preblast", "Edit Preblast"]:
        build_event_preblast_form(body, client, logger, context, region_record, event_id=event_id)
    elif action == "Take Q":
        DbManager.create_record(
            AttendanceNew(
                event_id=event_id,
                user_id=user_id,
                attendance_type_id=2,
                is_planned=True,
            )
        )
        # TODO: build the q / preblast form
        build_home_form(body, client, logger, context, region_record, update_view_id=view_id)
    elif action == "HC":
        DbManager.create_record(
            AttendanceNew(
                event_id=event_id,
                user_id=user_id,
                attendance_type_id=1,
                is_planned=True,
            )
        )
        build_home_form(body, client, logger, context, region_record, update_view_id=view_id)
    elif action == "Un-HC":
        DbManager.delete_records(
            cls=AttendanceNew,
            filters=[
                AttendanceNew.event_id == event_id,
                AttendanceNew.user_id == user_id,
                AttendanceNew.attendance_type_id == 1,
                AttendanceNew.is_planned,
            ],
        )
        build_home_form(body, client, logger, context, region_record, update_view_id=view_id)
    elif action == "edit":
        pass
