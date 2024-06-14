import json
from copy import deepcopy
from dataclasses import dataclass
from logging import Logger

from slack_sdk.web import WebClient

from utilities.database import DbManager, get_session
from utilities.database.orm import AttendanceNew, Event, EventType, Location, Org, Region, UserNew
from utilities.helper_functions import get_user_id, safe_get, time_int_to_str
from utilities.slack import actions, orm


@dataclass
class EventExtended:
    event: Event
    org: Org
    event_type: EventType
    location: Location


@dataclass
class AttendanceExtended:
    attendance: AttendanceNew
    user: UserNew


def build_event_preblast_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: Region,
    event_id: int = None,
    update_view_id: str = None,
):
    # event = DbManager.get_record(Event, event_id)
    with get_session() as session:
        query = (
            session.query(Event, Org, EventType, Location)
            .select_from(Event)
            .join(Org, Org.id == Event.org_id)
            .join(EventType, EventType.id == Event.event_type_id)
            .join(Location, Location.id == Event.location_id)
            .filter(Event.id == event_id)
        )
        record = EventExtended(*query.one_or_none())

        query = (
            session.query(AttendanceNew, UserNew)
            .join(UserNew)
            .filter(AttendanceNew.event_id == event_id, AttendanceNew.is_planned)
        )
        attendance_records = [AttendanceExtended(*r) for r in query.all()]

    action_blocks = []
    hc_list = " ".join([f"@{r.user.f3_name}" for r in attendance_records])
    hc_list = hc_list if hc_list else "None"
    hc_count = len({r.user.id for r in attendance_records})

    q_list = " ".join([f"@{r.user.f3_name}>" for r in attendance_records if r.attendance.attendance_type_id in [2, 3]])
    if not q_list:
        q_list = "Open!"
        action_blocks.append(
            orm.ButtonElement(
                label="Take Q",
                action=actions.EVENT_PREBLAST_TAKE_Q,
                value=str(record.event.id),
            )
        )

    user_id = get_user_id(safe_get(body, "user", "id") or safe_get(body, "user_id"), region_record, client, logger)
    user_hc = any(r.user.id == user_id for r in attendance_records)
    if user_hc:
        action_blocks.append(
            orm.ButtonElement(
                label="Un-HC",
                action=actions.EVENT_PREBLAST_UN_HC,
                value=str(record.event.id),
            )
        )
    else:
        action_blocks.append(
            orm.ButtonElement(
                label="HC",
                action=actions.EVENT_PREBLAST_HC,
                value=str(record.event.id),
            )
        )

    if safe_get(body, "actions", 0, "selected_option", "value") == "Edit Preblast":
        form = deepcopy(EVENT_PREBLAST_FORM)

        location_records: list[Location] = DbManager.find_records(Location, [Location.org_id == region_record.org_id])
        # TODO: filter locations to AO?
        # TODO: show hardcoded details (date, time, etc.)
        form.set_options(
            {
                actions.EVENT_PREBLAST_LOCATION: orm.as_selector_options(
                    names=[location.name for location in location_records],
                    values=[str(location.id) for location in location_records],
                ),
            }
        )
        form.set_initial_values(
            {
                actions.EVENT_PREBLAST_TITLE: record.event.name,
                actions.EVENT_PREBLAST_LOCATION: str(record.location.id),
                actions.EVENT_PREBLAST_MOLESKINE_EDIT: record.event.preblast_rich,
                actions.EVENT_PREBLAST_SEND_OPTIONS: "Send now",
            }
        )
        title_text = "Edit Event Preblast"
        submit_button_text = "Update"
        # TODO: take out the send block if AO not associated with a channel
        if not record.org.slack_id:
            form.blocks = form.blocks[:-1]
        else:
            form.blocks[-1].label = f"When would you like to send the preblast to <#{record.org.slack_id}>?"
    else:
        event_details = f"*Preblast: {record.event.name}*"
        event_details += f"\n*Date:* {record.event.start_date.strftime('%A, %B %d')}"
        event_details += f"\n*Start Time:* {time_int_to_str(record.event.start_time)}"
        event_details += f"\n*Location:* {record.org.name} - {record.location.name}"
        event_details += f"\n*Event Type:* {record.event_type.name}"
        event_details += f"\n*Q:* {q_list}"
        event_details += f"\n*HC Count:* {hc_count}"
        event_details += f"\n*HCs:* {hc_list}"
        blocks = [
            orm.SectionBlock(label=event_details),
            orm.RichTextBlock(label=record.event.preblast_rich or DEFAULT_PREBLAST),
            orm.ActionsBlock(elements=action_blocks),
        ]

        form = orm.BlockView(blocks=blocks)
        title_text = "Event Preblast"
        submit_button_text = "None"

    metadata = {
        "event_id": event_id,
    }

    if update_view_id:
        form.update_modal(
            client=client,
            view_id=update_view_id,
            title_text=title_text,
            submit_button_text=submit_button_text,
            parent_metadata=metadata,
            callback_id=actions.EVENT_PREBLAST_CALLBACK_ID,
        )
    else:
        form.post_modal(
            client=client,
            trigger_id=safe_get(body, "trigger_id"),
            callback_id=actions.EVENT_PREBLAST_CALLBACK_ID,
            title_text=title_text,
            submit_button_text=submit_button_text,
            new_or_add="add",
            parent_metadata=metadata,
        )


def handle_event_preblast_edit(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    form_data = EVENT_PREBLAST_FORM.get_selected_values(body)
    metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
    event_id = safe_get(metadata, "event_id")
    update_fields = {
        Event.name: form_data[actions.EVENT_PREBLAST_TITLE],
        Event.location_id: form_data[actions.EVENT_PREBLAST_LOCATION],
        Event.preblast_rich: form_data[actions.EVENT_PREBLAST_MOLESKINE_EDIT],
    }
    DbManager.update_record(Event, event_id, update_fields)

    if form_data[actions.EVENT_PREBLAST_SEND_OPTIONS] == "Send now":
        pass  # send preblast
    elif form_data[actions.EVENT_PREBLAST_SEND_OPTIONS] == "Schedule 24 hours before event":
        pass  # schedule preblast
    else:
        pass


def handle_event_preblast_hc(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
    event_id = safe_get(metadata, "event_id")
    user_id = get_user_id(safe_get(body, "user", "id") or safe_get(body, "user_id"), region_record, client, logger)
    view_id = safe_get(body, "view", "id")
    DbManager.create_record(
        AttendanceNew(
            event_id=event_id,
            user_id=user_id,
            attendance_type_id=1,
            is_planned=True,
        )
    )
    build_event_preblast_form(body, client, logger, context, region_record, event_id=event_id, update_view_id=view_id)


DEFAULT_PREBLAST = {
    "type": "rich_text",
    "elements": [{"type": "rich_text_section", "elements": [{"text": "No preblast entered yet!", "type": "text"}]}],
}

EVENT_PREBLAST_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Title",
            action=actions.EVENT_PREBLAST_TITLE,
            element=orm.PlainTextInputElement(
                placeholder="Event Title",
            ),
            optional=False,
            hint="Studies show that fun titles generate 42% more HC's!",
        ),
        orm.InputBlock(
            label="Location",
            action=actions.EVENT_PREBLAST_LOCATION,
            element=orm.StaticSelectElement(),
            optional=False,
        ),
        orm.InputBlock(
            label="Preblast",
            action=actions.EVENT_PREBLAST_MOLESKINE_EDIT,
            element=orm.RichTextInputElement(placeholder="Give us an event preview!"),
            optional=False,
        ),
        orm.InputBlock(
            label="When to send preblast?",
            action=actions.EVENT_PREBLAST_SEND_OPTIONS,
            element=orm.RadioButtonsElement(
                options=orm.as_selector_options(
                    names=["Send now", "Schedule 24 hours before event", "Do not send"],
                ),
            ),
            optional=False,
        ),
    ]
)
