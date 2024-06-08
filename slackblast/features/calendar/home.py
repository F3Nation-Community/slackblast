import datetime
from logging import Logger

from slack_sdk.web import WebClient

from utilities.database import DbManager
from utilities.database.orm import AttendanceNew, Event, Org, Region
from utilities.helper_functions import get_user_id, safe_convert, safe_get
from utilities.slack import actions, orm


def build_home_form(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region, update_view_id: str = None
):
    slack_user_id = safe_get(body, "user", "id") or safe_get(body, "user_id")
    user_id = get_user_id(slack_user_id, region_record, client, logger)
    blocks = [
        orm.SectionBlock(label="*Upcoming Schedule*"),
        orm.ActionsBlock(
            elements=[
                orm.StaticSelectElement(
                    placeholder="Filter AOs",
                    action=actions.CALENDAR_HOME_AO_FILTER,
                ),
                orm.StaticSelectElement(
                    placeholder="Filter Event Types",
                    action=actions.CALENDAR_HOME_EVENT_TYPE_FILTER,
                ),
                orm.DatepickerElement(
                    action=actions.CALENDAR_HOME_DATE_FILTER,
                    placeholder="Start Search Date",
                ),
                orm.CheckboxInputElement(
                    action=actions.CALENDAR_HOME_Q_FILTER,
                    options=orm.as_selector_options(names=["Show only open Q slots"], values=["yes"]),
                ),
            ],
        ),
    ]

    # Build the filter
    filter = [
        (Event.org_id == region_record.org_id) or (Org.parent_id == region_record.org_id),
        ~Event.is_series,
        Event.start_date < datetime.datetime.now() + datetime.timedelta(days=60),
        Event.start_date > datetime.datetime.now(),
    ]
    if safe_get(body, actions.CALENDAR_HOME_AO_FILTER):
        filter.append(Org.id == safe_convert(safe_get(body, actions.CALENDAR_HOME_AO_FILTER), int))

    if safe_get(body, actions.CALENDAR_HOME_EVENT_TYPE_FILTER):
        filter.append(Event.event_type_id == safe_convert(safe_get(body, actions.CALENDAR_HOME_EVENT_TYPE_FILTER), int))

    # Get the events
    events = DbManager.find_join_records2(Event, Org, filter)
    user_attendance = DbManager.find_records(
        AttendanceNew, [AttendanceNew.user_id == user_id, AttendanceNew.is_planned]
    )
    user_attendance = {x.event_id: x.attendance_type_id for x in user_attendance}
    events = sorted(events, key=lambda x: (x[0].start_date, x[1].name, x[0].start_time))

    # Build the event list
    active_date = datetime.date(2020, 1, 1)
    block_count = 1
    for event in events:
        if block_count > 90:
            break
        if event[0].start_date != active_date:
            active_date = event[0].start_date
            blocks.append(orm.SectionBlock(label=f":calendar: *{active_date.strftime('%A, %B %d')}*"))
            block_count += 1
        label = f"{event[0].name} @ {str(event[0].start_time).zfill(4)}\nQ: None"
        if user_attendance.get(event[0].id) == 1:
            label += "\n:white_check_mark: You HC'd!"
        blocks.append(
            orm.SectionBlock(
                label=label,
                element=orm.OverflowElement(
                    action=f"{actions.CALENDAR_HOME_EVENT}_{event[0].id}",
                    options=orm.as_selector_options(
                        # TODO: make dynamic if you've already taken a Q, HC'd, etc
                        names=["View Details", "Take Q", "HC", "Edit"],
                        values=["view", "take", "hc", "edit"],
                    ),
                ),
            )
        )
        block_count += 1

    form = orm.BlockView(blocks=blocks)
    form.update_modal(
        client=client,
        view_id=update_view_id or safe_get(body, actions.LOADING_ID),
        title_text="Calendar Home",
        callback_id=actions.CALENDAR_HOME_CALLBACK_ID,
        submit_button_text="None",
    )


def handle_home_event(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    event_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[1], int)
    action = safe_get(body, "actions", 0, "selected_option", "value")
    user_id = get_user_id(safe_get(body, "user", "id"), region_record, client, logger)
    view_id = safe_get(body, "view", "id")

    if action == "view":
        pass
    elif action == "take":
        pass
    elif action == "hc":
        DbManager.create_record(
            AttendanceNew(
                event_id=event_id,
                user_id=user_id,
                attendance_type_id=1,
                is_planned=True,
            )
        )
        build_home_form(body, client, logger, context, region_record, update_view_id=view_id)
    elif action == "edit":
        pass
