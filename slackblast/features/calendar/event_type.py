import copy
from logging import Logger

from slack_sdk.web import WebClient

from utilities.database import DbManager
from utilities.database.orm import EventCategory, EventType, EventType_x_Org, Region
from utilities.helper_functions import safe_get
from utilities.slack import actions, orm


def build_event_type_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    form = copy.deepcopy(EVENT_TYPE_FORM)

    # get event types that are not already in EventType_x_Org
    event_types = DbManager.find_records(EventType, [True])  # TODO: order by popularity, take out existing?
    event_types_org = DbManager.find_records(EventType_x_Org, [EventType_x_Org.org_id == region_record.org_id])
    event_types_org = [event_type_org.event_type_id for event_type_org in event_types_org]
    event_types = [event_type for event_type in event_types if event_type.id not in event_types_org]

    event_categories = DbManager.find_records(EventCategory, [True])
    form.set_options(
        {
            actions.CALENDAR_ADD_EVENT_TYPE_SELECT: orm.as_selector_options(
                names=[event_type.name for event_type in event_types],
                values=[str(event_type.id) for event_type in event_types],
            ),
            actions.CALENDAR_ADD_EVENT_TYPE_CATEGORY: orm.as_selector_options(
                names=[event_category.name for event_category in event_categories],
                values=[str(event_category.id) for event_category in event_categories],
                descriptions=[event_category.description for event_category in event_categories],
            ),
        }
    )

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Add an Event Type",
        callback_id=actions.CALENDAR_ADD_EVENT_TYPE_CALLBACK_ID,
        new_or_add="add",
    )


def handle_event_type_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    form_data = EVENT_TYPE_FORM.get_selected_values(body)
    event_type_name = form_data.get(actions.CALENDAR_ADD_EVENT_TYPE_NEW)
    event_type_id = form_data.get(actions.CALENDAR_ADD_EVENT_TYPE_SELECT)
    event_category_id = form_data.get(actions.CALENDAR_ADD_EVENT_TYPE_CATEGORY)

    if event_type_id:
        DbManager.create_record(
            EventType_x_Org(
                org_id=region_record.org_id,
                event_type_id=event_type_id,
                is_default=False,
            )
        )

    elif event_type_name and event_category_id:
        event_type = DbManager.create_record(
            EventType(
                name=event_type_name,
                category_id=event_category_id,
            )
        )
        DbManager.create_record(
            EventType_x_Org(
                org_id=region_record.org_id,
                event_type_id=event_type.id,
                is_default=False,
            )
        )


EVENT_TYPE_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Select from commonly used event types",
            element=orm.StaticSelectElement(placeholder="Select from commonly used event types"),
            optional=True,
            action=actions.CALENDAR_ADD_EVENT_TYPE_SELECT,
        ),
        orm.DividerBlock(),
        orm.InputBlock(
            label="Or create a new event type",
            element=orm.PlainTextInputElement(placeholder="New event type"),
            action=actions.CALENDAR_ADD_EVENT_TYPE_NEW,
            optional=True,
        ),
        orm.InputBlock(
            label="Select an event category",
            element=orm.StaticSelectElement(placeholder="Select an event category"),
            action=actions.CALENDAR_ADD_EVENT_TYPE_CATEGORY,
            optional=True,
            hint="If entering a new event type, this is required for national aggregations (achievements, etc).",
        ),
        orm.InputBlock(
            label="Event type acronym",
            element=orm.PlainTextInputElement(placeholder="Two letter acronym", max_length=2),
            action=actions.CALENDAR_ADD_EVENT_TYPE_ACRONYM,
            optional=True,
            hint="This is used for the calendar view to save on space. Defaults to first two letters of event type name. Make sure it's unique!",  # noqa
        ),
    ]
)
