import copy
from logging import Logger

from slack_sdk.web import WebClient

from utilities.database import DbManager
from utilities.database.orm import EventTag, EventTag_x_Org, Region
from utilities.helper_functions import safe_get
from utilities.slack import actions, orm


def build_event_tag_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    form = copy.deepcopy(EVENT_TAG_FORM)

    # get event types that are not already in EventType_x_Org
    event_tags = DbManager.find_join_records2(EventTag, EventTag_x_Org, [True])
    event_tags_new: list[EventTag] = [event_tag[0] for event_tag in event_tags if event_tag[1] is None]
    event_tags_org: list[EventTag] = [event_tag[0] for event_tag in event_tags if event_tag[1] is not None]

    form.set_options(
        {
            actions.CALENDAR_ADD_EVENT_TYPE_SELECT: orm.as_selector_options(
                names=[event_type.name for event_type in event_tags_new],
                values=[str(event_type.id) for event_type in event_tags_new],
                descriptions=[event_type.color for event_type in event_tags_new],
            ),
        }
    )

    # set list of colors already in use
    color_list = [f"{e.name} - {e.color}" for e in event_tags_org]
    form.blocks[-1].label = f"Colors already in use: \n - {'\n - '.join(color_list)}"

    form.post_modal(
        client=client,
        trigger_id=safe_get(body, "trigger_id"),
        title_text="Add an Event Tag",
        callback_id=actions.CALENDAR_ADD_EVENT_TYPE_CALLBACK_ID,
        new_or_add="add",
    )


def handle_event_tag_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    form_data = EVENT_TAG_FORM.get_selected_values(body)
    event_tag_name = form_data.get(actions.CALENDAR_ADD_EVENT_TAG_NEW)
    event_tag_id = form_data.get(actions.CALENDAR_ADD_EVENT_TAG_SELECT)
    event_color = form_data.get(actions.CALENDAR_ADD_EVENT_TAG_COLOR)

    if event_tag_id:
        DbManager.create_record(
            EventTag_x_Org(
                org_id=region_record.org_id,
                event_type_id=event_tag_id,
            )
        )

    elif event_tag_name and event_color:
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
                is_default=False,
            )
        )


EVENT_TAG_COLORS = {
    "Red": "#FF0000",
    "Orange": "#FFA500",
    "Yellow": "#FFFF00",
    "Green": "#008000",
    "Blue": "#0000FF",
    "Purple": "#800080",
    "Pink": "#FFC0CB",
    "Black": "#000000",
    "White": "#FFFFFF",
    "Gray": "#808080",
    "Brown": "#A52A2A",
    "Cyan": "#00FFFF",
    "Magenta": "#FF00FF",
    "Lime": "#00FF00",
    "Teal": "#008080",
    "Indigo": "#4B0082",
    "Maroon": "#800000",
    "Navy": "#000080",
    "Olive": "#808000",
    "Silver": "#C0C0C0",
    "Sky": "#87CEEB",
    "Gold": "#FFD700",
    "Coral": "#FF7F50",
    "Salmon": "#FA8072",
    "Turquoise": "#40E0D0",
    "Lavender": "#E6E6FA",
    "Beige": "#F5F5DC",
    "Mint": "#98FF98",
    "Peach": "#FFDAB9",
    "Ivory": "#FFFFF0",
    "Khaki": "#F0E68C",
    "Crimson": "#DC143C",
    "Violet": "#EE82EE",
    "Plum": "#DDA0DD",
    "Azure": "#F0FFFF",
}

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
