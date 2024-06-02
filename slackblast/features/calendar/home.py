import datetime
import json
from logging import Logger

from slack_sdk.web import WebClient

from utilities.database import DbManager
from utilities.database.orm import Event, Org, Region
from utilities.helper_functions import safe_convert, safe_get
from utilities.slack import actions, orm


def build_home_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
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
        Event.start_date < datetime.datetime.now() + datetime.timedelta(days=14),
        Event.start_date > datetime.datetime.now(),
    ]
    if safe_get(body, actions.CALENDAR_HOME_AO_FILTER):
        filter.append(Org.id == safe_convert(safe_get(body, actions.CALENDAR_HOME_AO_FILTER), int))

    if safe_get(body, actions.CALENDAR_HOME_EVENT_TYPE_FILTER):
        filter.append(Event.event_type_id == safe_convert(safe_get(body, actions.CALENDAR_HOME_EVENT_TYPE_FILTER), int))

    # Get the events
    events = DbManager.find_join_records2(Event, Org, filter)
    events = sorted(events, key=lambda x: (x[0].start_date, x[1].name, x[0].start_time))

    # Build the event list
    active_date = datetime.date(2020, 1, 1)
    # action_elements = []
    for event in events:
        if event[0].start_date != active_date:
            # if action_elements:
            #     blocks.append(orm.ActionsBlock(elements=action_elements))
            # action_elements = []

            active_date = event[0].start_date
            blocks.append(orm.SectionBlock(label=f":calendar: *{active_date.strftime('%A, %B %d')}*"))
        blocks.append(
            orm.SectionBlock(
                label=f"{event[0].name} @ {str(event[0].start_time).zfill(4)}\nQ: None",
                element=orm.OverflowElement(
                    action=f"{actions.CALENDAR_HOME_EVENT}_{event[0].id}",
                    options=orm.as_selector_options(
                        names=["View Details", "Take Q", "HC"], values=["view", "take", "HC"]
                    ),
                ),
            )
        )
        # action_elements.append(
        #     orm.ButtonElement(  # this is kind of fugly... what else could we use?
        #         label=f"{event[0].name} @ {str(event[0].start_time).zfill(4)} Q: None",
        #         action=f"{actions.CALENDAR_HOME_EVENT}_{event[0].id}",
        #         value=str(event[0].id),
        #     )
        # )
    # blocks.append(orm.ActionsBlock(elements=action_elements))

    form = orm.BlockView(blocks=blocks)
    print(json.dumps(form.as_form_field(), indent=4))
    form.update_modal(
        client=client,
        view_id=safe_get(body, actions.LOADING_ID),
        title_text="Calendar Home",
        callback_id=actions.CALENDAR_HOME_CALLBACK_ID,
        submit_button_text="None",
    )
