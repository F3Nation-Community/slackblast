import copy
import json
from logging import Logger

from slack_sdk.web import WebClient

from utilities.constants import EVENT_TAG_COLORS
from utilities.database import DbManager
from utilities.database.orm import EventTag, EventTag_x_Org, Org, SlackSettings
from utilities.helper_functions import safe_convert, safe_get
from utilities.slack import actions, orm


def manage_event_tags(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "add":
        build_event_tag_form(body, client, logger, context, region_record)
    elif action == "edit":
        build_event_tag_list_form(body, client, logger, context, region_record)


def build_event_tag_form(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: SlackSettings,
    edit_event_tag: EventTag_x_Org = None,
):
    form = copy.deepcopy(EVENT_TAG_FORM)

    # get event types that are not already in EventType_x_Org
    event_tags = DbManager.find_join_records3(EventTag, EventTag_x_Org, Org, [True], left_join=True)
    event_tags_new: list[EventTag] = [event_tag[0] for event_tag in event_tags if event_tag[1] is None]
    event_tags_org: list[EventTag] = [event_tag for event_tag in event_tags if event_tag[1] is not None]

    if edit_event_tag:
        event_tag = DbManager.get_record(EventTag, edit_event_tag.event_tag_id)
        form.set_initial_values(
            {
                actions.CALENDAR_ADD_EVENT_TAG_NEW: event_tag.name,
                actions.CALENDAR_ADD_EVENT_TAG_COLOR: edit_event_tag.color_override or event_tag.color,
            }
        )
        form.blocks.pop(0)
        form.blocks.pop(0)
        form.blocks[0].label = "Edit Event Tag"
        form.blocks[0].element.placeholder = "Edit Event Tag"
        title_text = "Edit an Event Tag"
        metadata = {"edit_event_tag_org_id": edit_event_tag.id}
    else:
        form.set_options(
            {
                actions.CALENDAR_ADD_EVENT_TAG_SELECT: orm.as_selector_options(
                    names=[event_tag.name for event_tag in event_tags_new],
                    values=[str(event_tag.id) for event_tag in event_tags_new],
                    descriptions=[event_tag.color for event_tag in event_tags_new],
                ),
            }
        )
        title_text = "Add an Event Tag"
        metadata = {}

    # set list of colors already in use
    color_list = [f"{e[0].name} - {e[1].color_override or e[0].color}" for e in event_tags_org]
    form.blocks[-1].label = f"Colors already in use: \n - {'\n - '.join(color_list)}"

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text=title_text,
        callback_id=actions.CALENDAR_ADD_EVENT_TAG_CALLBACK_ID,
        new_or_add="add",
        parent_metadata=metadata,
    )


def handle_event_tag_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings):
    form_data = EVENT_TAG_FORM.get_selected_values(body)
    event_tag_name = form_data.get(actions.CALENDAR_ADD_EVENT_TAG_NEW)
    event_tag_id = form_data.get(actions.CALENDAR_ADD_EVENT_TAG_SELECT)
    event_color = form_data.get(actions.CALENDAR_ADD_EVENT_TAG_COLOR)
    metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
    edit_event_tag_org_id = safe_convert(metadata.get("edit_event_tag_org_id"), int)

    if event_tag_id:
        DbManager.create_record(
            EventTag_x_Org(
                org_id=region_record.org_id,
                event_tag_id=event_tag_id,
                color_override=event_color,
            )
        )

    elif event_tag_name and event_color:
        if edit_event_tag_org_id:
            DbManager.update_record(
                EventTag_x_Org,
                edit_event_tag_org_id,
                {EventTag_x_Org.color_override: event_color},
            )
        else:
            event_tag = DbManager.create_record(
                EventTag(
                    name=event_tag_name,
                    color=event_color,
                )
            )
            DbManager.create_record(
                EventTag_x_Org(
                    org_id=region_record.org_id,
                    event_tag_id=event_tag.id,
                    color_override=event_color,
                )
            )


def build_event_tag_list_form(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    event_tag_records: list[tuple[EventTag, EventTag_x_Org]] = DbManager.find_join_records2(
        EventTag, EventTag_x_Org, [EventTag_x_Org.org_id == region_record.org_id]
    )

    blocks = [
        orm.SectionBlock(
            label=s[0].name,
            action=f"{actions.EVENT_TAG_EDIT_DELETE}_{s[1].id}",
            element=orm.StaticSelectElement(
                placeholder="Edit or Delete",
                options=orm.as_selector_options(names=["Edit", "Delete"]),
                confirm=orm.ConfirmObject(
                    title="Are you sure?",
                    text="Are you sure you want to edit / delete this Event Tag? This cannot be undone.",
                    confirm="Yes, I'm sure",
                    deny="Whups, never mind",
                ),
            ),
        )
        for s in event_tag_records
    ]

    form = orm.BlockView(blocks=blocks)
    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Edit/Delete an Event Tag",
        callback_id=actions.EDIT_DELETE_AO_CALLBACK_ID,
        submit_button_text="None",
        new_or_add="add",
    )


def handle_event_tag_edit_delete(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: SlackSettings
):
    event_tag_org_id = safe_convert(safe_get(body, "actions", 0, "action_id").split("_")[1], int)
    action = safe_get(body, "actions", 0, "selected_option", "value")

    if action == "Edit":
        event_tag_org = DbManager.get_record(EventTag_x_Org, event_tag_org_id)
        build_event_tag_form(body, client, logger, context, region_record, edit_event_tag=event_tag_org)
    elif action == "Delete":
        DbManager.delete_record(EventTag_x_Org, event_tag_org_id)


EVENT_TAG_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Select from commonly used event tags",
            element=orm.StaticSelectElement(placeholder="Select from commonly used event tags"),
            optional=True,
            action=actions.CALENDAR_ADD_EVENT_TAG_SELECT,
        ),
        orm.DividerBlock(),
        orm.InputBlock(
            label="Or create a new event tag",
            element=orm.PlainTextInputElement(placeholder="New event tag"),
            action=actions.CALENDAR_ADD_EVENT_TAG_NEW,
            optional=True,
        ),
        orm.InputBlock(
            label="Event tag color",
            element=orm.StaticSelectElement(
                placeholder="Select a color",
                options=orm.as_selector_options(names=list(EVENT_TAG_COLORS.keys())),
            ),
            action=actions.CALENDAR_ADD_EVENT_TAG_COLOR,
            optional=True,
            hint="This is the color that will be shown on the calendar",
        ),
        orm.SectionBlock(label="Colors already in use:"),
    ]
)
