import copy
import json
import os
from datetime import date, datetime
from logging import Logger

import pytz
from cryptography.fernet import Fernet
from pillow_heif import register_heif_opener
from slack_sdk.web import WebClient
from sqlalchemy import not_

from utilities import constants, sendmail
from utilities.database import DbManager
from utilities.database.orm import (
    Attendance,
    AttendanceNew,
    Backblast,
    Event,
    PaxminerUser,
    Region,
)
from utilities.database.special_queries import event_attendance_query, event_preblast_query
from utilities.helper_functions import (
    check_for_duplicate,
    get_channel_id,
    get_channel_name,
    get_pax,
    get_user,
    get_user_names,
    parse_rich_block,
    plain_text_to_rich_block,
    remove_keys_from_dict,
    replace_user_channel_ids,
    safe_convert,
    safe_get,
    upload_files_to_s3,
)
from utilities.slack import actions, forms
from utilities.slack import orm as slack_orm

register_heif_opener()


def add_custom_field_blocks(form: slack_orm.BlockView, region_record: Region) -> slack_orm.BlockView:
    output_form = copy.deepcopy(form)
    for custom_field in (region_record.custom_fields or {}).values():
        if safe_get(custom_field, "enabled"):
            output_form.add_block(
                slack_orm.InputBlock(
                    element=forms.CUSTOM_FIELD_TYPE_MAP[custom_field["type"]],
                    action=actions.CUSTOM_FIELD_PREFIX + custom_field["name"],
                    label=custom_field["name"],
                    optional=True,
                )
            )
            if safe_get(custom_field, "type") == "Dropdown":
                output_form.set_options(
                    {
                        actions.CUSTOM_FIELD_PREFIX + custom_field["name"]: slack_orm.as_selector_options(
                            names=custom_field["options"],
                            values=custom_field["options"],
                        )
                    }
                )
    return output_form


def backblast_middleware(
    body: dict,
    client: WebClient,
    logger: Logger,
    context: dict,
    region_record: Region,
):
    user = get_user(safe_get(body, "user", "id") or safe_get(body, "user_id"), region_record, client, logger)
    user_id = user.user_id
    event_records = event_attendance_query(
        attendance_filter=[
            AttendanceNew.user_id == user_id,
            AttendanceNew.is_planned,
            AttendanceNew.attendance_type_id.in_([2, 3]),
        ],
        event_filter=[
            Event.start_date < date.today(),
            Event.backblast_ts.is_(None),
            Event.is_active,
        ],
    )

    if event_records:
        select_block = slack_orm.InputBlock(
            label="Select a past Q",
            action=actions.BACKBLAST_FILL_SELECT,
            dispatch_action=True,
            element=slack_orm.StaticSelectElement(
                placeholder="Select an event",
                options=slack_orm.as_selector_options(
                    names=[f"{r.event.start_date} {r.org.name} {r.event_type.name}" for r in event_records],
                    values=[str(r.event.id) for r in event_records],
                ),
            ),
        )
    else:
        select_block = slack_orm.SectionBlock(label="No past events for you to send a backblast for!")

    blocks = [
        select_block,
        slack_orm.ActionsBlock(
            elements=[
                slack_orm.ButtonElement(
                    label=":heavy_plus_sign: New Unscheduled Event", action=actions.BACKBLAST_NEW_BLANK_BUTTON
                ),
                slack_orm.ButtonElement(label=":calendar: Open Calendar", action=actions.OPEN_CALENDAR_BUTTON),
            ]
        ),
    ]
    form = slack_orm.BlockView(blocks=blocks)
    form.update_modal(
        client=client,
        view_id=safe_get(body, actions.LOADING_ID),
        callback_id=actions.BACKBLAST_SELECT_CALLBACK_ID,
        title_text="Select Backblast",
        submit_button_text="None",
    )


def build_backblast_form_new(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    """
    Args:
        body (dict): Slack request body
        client (WebClient): Slack WebClient object
        logger (Logger): Logger object
        context (dict): Slack request context
        region_record (Region): Region record for the requesting region
    """

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    trigger_id = safe_get(body, "trigger_id")
    backblast_metadata = safe_get(body, "message", "metadata", "event_payload") or {}
    action_id = safe_get(body, "actions", 0, "action_id")
    if action_id == actions.BACKBLAST_FILL_SELECT:
        event_id = safe_convert(safe_get(body, "actions", 0, "selected_option", "value"), int)
    else:
        event_id = safe_get(backblast_metadata, "event_id")

    update_view_id = safe_get(body, actions.LOADING_ID) or safe_get(body, "view", "id")

    if safe_get(backblast_metadata, actions.BACKBLAST_TITLE):
        initial_backblast_data = backblast_metadata
        moleskin_block = safe_get(body, "message", "blocks", 1)
        moleskin_block = remove_keys_from_dict(moleskin_block, ["display_team_id", "display_url"])
        initial_backblast_data[actions.BACKBLAST_MOLESKIN] = moleskin_block
    elif event_id:
        event_record, attendance_records = event_preblast_query(event_id)
        initial_backblast_data = {
            actions.BACKBLAST_TITLE: event_record.event.name,
            actions.BACKBLAST_DATE: event_record.event.start_date.strftime("%Y-%m-%d"),
            actions.BACKBLAST_AO: event_record.org.slack_id,
            actions.BACKBLAST_Q: safe_get(
                [a.slack_user.slack_id for a in attendance_records if a.attendance.attendance_type_id == 2], 0
            ),
            actions.BACKBLAST_COQ: [
                a.slack_user.user_id for a in attendance_records if a.attendance.attendance_type_id == 3
            ],
            actions.BACKBLAST_PAX: [a.slack_user.slack_id for a in attendance_records],
            actions.BACKBLAST_MOLESKIN: region_record.backblast_moleskin_template,
        }
        backblast_metadata["event_id"] = event_id
    else:
        initial_backblast_data = {
            actions.BACKBLAST_Q: user_id,
            actions.BACKBLAST_DATE: datetime.now(pytz.timezone("US/Central")).strftime("%Y-%m-%d"),
            actions.BACKBLAST_MOLESKIN: region_record.backblast_moleskin_template,
        }

    backblast_form = copy.deepcopy(forms.BACKBLAST_FORM)
    backblast_form.set_initial_values(initial_backblast_data)
    backblast_form = add_custom_field_blocks(backblast_form, region_record)

    if not (region_record.email_enabled & region_record.email_option_show):
        backblast_form.delete_block(actions.BACKBLAST_EMAIL_SEND)
    # backblast_metadata = None
    if action_id == actions.BACKBLAST_EDIT_BUTTON:
        callback_id = actions.BACKBLAST_EDIT_CALLBACK_ID
        backblast_metadata["channel_id"] = safe_get(body, "container", "channel_id")
        backblast_metadata["message_ts"] = safe_get(body, "container", "message_ts")
        backblast_metadata["files"] = safe_get(backblast_metadata, actions.BACKBLAST_FILE) or []
    else:
        callback_id = actions.BACKBLAST_CALLBACK_ID

    if update_view_id:
        backblast_form.update_modal(
            client=client,
            view_id=update_view_id,
            callback_id=callback_id,
            title_text="Backblast",
            parent_metadata=backblast_metadata,
        )
    else:
        backblast_form.post_modal(
            client=client,
            trigger_id=trigger_id,
            callback_id=callback_id,
            title_text="Backblast",
            parent_metadata=backblast_metadata,
        )


def handle_backblast_post_new(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    create_or_edit = "create" if safe_get(body, "view", "callback_id") == actions.BACKBLAST_CALLBACK_ID else "edit"

    backblast_form = copy.deepcopy(forms.BACKBLAST_FORM)
    backblast_form = add_custom_field_blocks(backblast_form, region_record)
    backblast_data: dict = backblast_form.get_selected_values(body)
    logger.debug(f"Backblast data: {backblast_data}")

    title = safe_get(backblast_data, actions.BACKBLAST_TITLE)
    the_date = safe_get(backblast_data, actions.BACKBLAST_DATE)
    the_ao = safe_get(backblast_data, actions.BACKBLAST_AO)
    the_q = safe_get(backblast_data, actions.BACKBLAST_Q)
    the_coq = safe_get(backblast_data, actions.BACKBLAST_COQ)
    pax = safe_get(backblast_data, actions.BACKBLAST_PAX)
    non_slack_pax = safe_get(backblast_data, actions.BACKBLAST_NONSLACK_PAX)
    fngs = safe_get(backblast_data, actions.BACKBLAST_FNGS)
    count = safe_get(backblast_data, actions.BACKBLAST_COUNT)
    moleskin = safe_get(backblast_data, actions.BACKBLAST_MOLESKIN)
    email_send = safe_get(backblast_data, actions.BACKBLAST_EMAIL_SEND)
    # ao = safe_get(backblast_data, actions.BACKBLAST_AO)
    files = safe_get(backblast_data, actions.BACKBLAST_FILE) or []

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    file_list, file_send_list = upload_files_to_s3(files=files, user_id=user_id, logger=logger, client=client)
    metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
    event_id = safe_get(metadata, "event_id")
    if (
        region_record.default_destination == constants.CONFIG_DESTINATION_SPECIFIED["value"]
        and region_record.destination_channel
    ):
        destination_channel = region_record.destination_channel
    else:
        destination_channel = the_ao

    if create_or_edit == "edit":
        message_channel = safe_get(metadata, "channel_id")
        message_ts = safe_get(metadata, "message_ts")
        file_list = safe_get(metadata, "files") if not file_list else file_list
    else:
        message_channel = None
        message_ts = None

    all_pax = list(set([the_q] + (the_coq or []) + pax))
    db_users = [get_user(p, region_record, client, logger) for p in all_pax]
    auto_count = len(all_pax)
    pax_names_list = [user.user_name for user in db_users]

    pax_formatted = get_pax(pax)
    pax_full_list = [pax_formatted]
    fngs_formatted = fngs
    fng_count = 0
    if non_slack_pax:
        pax_full_list.append(non_slack_pax)
        pax_names_list.append(non_slack_pax)
        auto_count += non_slack_pax.count(",") + 1
    if fngs:
        pax_full_list.append(fngs)
        pax_names_list.append(fngs)
        fng_count = fngs.count(",") + 1
        fngs_formatted = str(fng_count) + " " + fngs
        auto_count += fngs.count(",") + 1
    pax_formatted = ", ".join(pax_full_list)
    pax_names = ", ".join(pax_names_list)

    if the_coq is None:
        the_coqs_formatted = ""
        the_coqs_names = ""
    else:
        the_coqs_formatted = get_pax(the_coq)
        the_coqs_full_list = [the_coqs_formatted]
        the_coqs_users = [get_user(c, region_record, client, logger) for c in the_coq]
        the_coqs_names_list = [user.user_name for user in the_coqs_users]
        the_coqs_formatted = ", " + ", ".join(the_coqs_full_list)
        the_coqs_names = ", " + ", ".join(the_coqs_names_list)

    ao_name = get_channel_name(the_ao, logger, client, region_record)
    q_user = get_user(the_q, region_record, client, logger)
    q_name = q_user.user_name
    q_url = q_user.avatar_url
    count = count or auto_count

    post_msg = f"""*Backblast! {title}*
*DATE*: {the_date}
*AO*: <#{the_ao}>
*Q*: <@{the_q}>{the_coqs_formatted}
*PAX*: {pax_formatted}
*FNGs*: {fngs_formatted}
*COUNT*: {count}"""

    custom_fields = {}
    for field, value in backblast_data.items():
        if (field[: len(actions.CUSTOM_FIELD_PREFIX)] == actions.CUSTOM_FIELD_PREFIX) and value:
            post_msg += f"\n*{field[len(actions.CUSTOM_FIELD_PREFIX):]}*: {str(value)}"
            custom_fields[field[len(actions.CUSTOM_FIELD_PREFIX) :]] = value

    if file_list:
        custom_fields["files"] = file_list

    msg_block = slack_orm.SectionBlock(label=post_msg)

    backblast_data.pop(actions.BACKBLAST_MOLESKIN, None)
    backblast_data[actions.BACKBLAST_FILE] = file_list
    backblast_data[actions.BACKBLAST_OP] = user_id
    backblast_data["event_id"] = event_id

    edit_block = slack_orm.ActionsBlock(
        elements=[
            slack_orm.ButtonElement(
                label=":pencil: Edit this backblast",
                action=actions.BACKBLAST_EDIT_BUTTON,
                value=json.dumps(backblast_data),
            ),
            slack_orm.ButtonElement(
                label=":heavy_plus_sign: New backblast",
                action=actions.BACKBLAST_NEW_BUTTON,
                value="new",
            ),
        ]
    )

    if region_record.strava_enabled:
        edit_block.elements.append(
            slack_orm.ButtonElement(
                label=":runner: Connect to Strava",
                action=actions.BACKBLAST_STRAVA_BUTTON,
                value="strava",
            )
        )

    blocks = [msg_block.as_form_field(), moleskin]
    for file in file_list or []:
        blocks.append(
            slack_orm.ImageBlock(
                alt_text=title,
                image_url=file,
            ).as_form_field()
        )
    blocks.append(edit_block.as_form_field())

    moleskin_text = parse_rich_block(moleskin)
    moleskin_text_w_names = replace_user_channel_ids(
        moleskin_text, region_record, client, logger
    )  # check this for efficiency

    if create_or_edit == "create":
        text = (f"{moleskin_text_w_names}\n\nUse the 'New Backblast' button to create a new backblast")[:1500]
        res = client.chat_postMessage(
            channel=destination_channel,
            text=text,
            username=f"{q_name} (via Slackblast)",
            icon_url=q_url,
            blocks=blocks,
            metadata={"event_type": "backblast", "event_payload": backblast_data},
        )
        print(json.dumps({"event_type": "successful_slack_post", "team_name": region_record.workspace_name}))
        if (email_send and email_send == "yes") or (email_send is None and region_record.email_enabled == 1):
            moleskin_msg = moleskin_text_w_names

            if region_record.postie_format:
                subject = f"[{ao_name}] {title}"
                moleskin_msg += f"\n\nTags: {ao_name}, {pax_names}"
            else:
                subject = title

            email_msg = f"""Date: {the_date}
AO: {ao_name}
Q: {q_name} {the_coqs_names}
PAX: {pax_names}
FNGs: {fngs_formatted}
COUNT: {count}
{moleskin_msg}
            """

            try:
                # Decrypt password
                fernet = Fernet(os.environ[constants.PASSWORD_ENCRYPT_KEY].encode())
                email_password_decrypted = fernet.decrypt(region_record.email_password.encode()).decode()
                sendmail.send(
                    subject=subject,
                    body=email_msg,
                    email_server=region_record.email_server,
                    email_server_port=region_record.email_server_port,
                    email_user=region_record.email_user,
                    email_password=email_password_decrypted,
                    email_to=region_record.email_to,
                    attachments=file_send_list,
                )
                logger.debug("\nEmail Sent! \n{}".format(email_msg))
                print(
                    json.dumps(
                        {
                            "event_type": "successful_email_sent",
                            "team_name": region_record.workspace_name,
                        }
                    )
                )
            except Exception as sendmail_err:
                logger.error("Error with sendmail: {}".format(sendmail_err))
                logger.debug("\nEmail Sent! \n{}".format(email_msg))
                print(json.dumps({"event_type": "failed_email", "team_name": region_record.workspace_name}))

    elif create_or_edit == "edit":
        text = (f"{moleskin_text_w_names}\n\nUse the 'New Backblast' button to create a new backblast")[:1500]
        res = client.chat_update(
            channel=message_channel,
            ts=message_ts,
            text=text,
            username=f"{q_name} (via Slackblast)",
            icon_url=q_url,
            blocks=blocks,
            metadata={"event_type": "backblast", "event_payload": backblast_data},
        )
        logger.debug("\nBackblast updated in Slack! \n{}".format(post_msg))
        print(json.dumps({"event_type": "successful_slack_edit", "team_name": region_record.workspace_name}))

        if event_id:
            DbManager.delete_records(
                AttendanceNew,
                filters=[
                    AttendanceNew.event_id == event_id,
                    not_(AttendanceNew.is_planned),
                ],
            )
        logger.debug("\nBackblast deleted from database! \n{}".format(post_msg))
        print(json.dumps({"event_type": "successful_db_delete", "team_name": region_record.workspace_name}))

    # res_link = client.chat_getPermalink(channel=chan or message_channel, message_ts=res["ts"])

    backblast_parsed = f"""Backblast! {title}
Date: {the_date}
AO: {ao_name}
Q: {q_name} {the_coqs_names}
PAX: {pax_names}
FNGs: {fngs_formatted}
COUNT: {count}
{moleskin_text_w_names}
"""
    rich_blocks: list = res["message"]["blocks"]
    rich_blocks.pop(-1)
    db_fields = {
        Event.start_date: the_date,
        Event.backblast_ts: res["ts"],
        Event.backblast: backblast_parsed,
        Event.backblast_rich: res["message"]["blocks"],
        Event.name: title,
        Event.pax_count: count,
        Event.fng_count: fng_count,
        Event.meta: custom_fields,
    }
    if event_id:
        DbManager.update_record(Event, event_id, fields=db_fields)
    else:
        db_fields = {k.key: v for k, v in db_fields.items()}
        event = DbManager.create_record(Event(**db_fields))
        event_id = event.id

    attendance_types = [2 if u.slack_id == the_q else 3 if u.slack_id in (the_coq or []) else 1 for u in db_users]
    attendance_records = [
        AttendanceNew(
            event_id=event_id,
            user_id=user.user_id,
            attendance_type_id=attendance_type,
            is_planned=False,
        )
        for user, attendance_type in zip(db_users, attendance_types)
    ]
    DbManager.create_records(attendance_records)
    print(
        json.dumps(
            {
                "event_type": "successful_db_insert",
                "team_name": region_record.workspace_name,
            }
        )
    )

    for file in file_send_list:
        try:
            os.remove(file["filepath"])
        except Exception as e:
            logger.error(f"Error removing file: {e}")


def build_backblast_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    """This function builds the backblast form and posts it to Slack. There are several entry points for this function:
        1. Building a new backblast, either through the /backblast command or the "New Backblast" button
        2. Editing an existing backblast, invoked by the "Edit Backblast" button
        3. Duplicate checking, invoked by the "Q", "Date", or "AO" fields being changed

    Args:
        body (dict): Slack request body
        client (WebClient): Slack WebClient object
        logger (Logger): Logger object
        context (dict): Slack request context
        region_record (Region): Region record for the requesting region
    """

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")
    channel_name = safe_get(body, "channel_name") or safe_get(body, "channel", "name")
    trigger_id = safe_get(body, "trigger_id")
    action_id = safe_get(body, "actions", 0, "action_id")
    if action_id == actions.BACKBLAST_FILL_SELECT:
        event_id = safe_convert(safe_get(body, "actions", 0, "selected_option", "value"), int)
    else:
        event_id = None

    for block in safe_get(body, "view", "blocks") or []:
        if not channel_id and block["block_id"] == actions.BACKBLAST_DESTINATION:
            channel_id = block["element"]["options"][1]["value"]
            channel_name = get_channel_name(channel_id, logger, client, region_record)

    if (
        (safe_get(body, "command") in ["/backblast", "/slackblast"])  # won't happen anymore
        or (safe_get(body, "actions", 0, "action_id") == actions.BACKBLAST_NEW_BUTTON)  # won't happen anymore
        or (safe_get(body, "view", "callback_id") == actions.BACKBLAST_CALLBACK_ID)
        or event_id
    ):
        backblast_method = "create"
        update_view_id = safe_get(body, "view", "id") or safe_get(body, actions.LOADING_ID)
        duplicate_check = False
        parent_metadata = {}
    else:
        backblast_method = "edit"
        update_view_id = (
            safe_get(body, "view", "id") or safe_get(body, "container", "view_id") or safe_get(body, actions.LOADING_ID)
        )
        duplicate_check = safe_get(body, "view", "callback_id") == actions.BACKBLAST_EDIT_CALLBACK_ID
        parent_metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")

    if safe_get(body, "actions", 0, "action_id") in [
        actions.BACKBLAST_AO,
        actions.BACKBLAST_DATE,
        actions.BACKBLAST_Q,
    ]:
        logger.debug("running duplicate check")
        duplicate_check = True
        update_view_id = safe_get(body, "view", "id") or safe_get(body, "container", "view_id")
        initial_backblast_data = forms.BACKBLAST_FORM.get_selected_values(body)
    elif (safe_get(body, "view", "callback_id") == actions.BACKBLAST_EDIT_CALLBACK_ID) or (
        safe_get(body, "actions", 0, "action_id") == actions.BACKBLAST_EDIT_BUTTON
    ):
        initial_backblast_data = safe_get(body, "message", "metadata", "event_payload") or json.loads(
            safe_get(body, "actions", 0, "value") or "{}"
        )
        if not safe_get(initial_backblast_data, actions.BACKBLAST_MOLESKIN):
            moleskin_block = safe_get(body, "message", "blocks", 1)
            moleskin_block = remove_keys_from_dict(moleskin_block, ["display_team_id", "display_url"])
            if moleskin_block.get("type") == "section":
                initial_backblast_data[actions.BACKBLAST_MOLESKIN] = plain_text_to_rich_block(
                    moleskin_block["text"]["text"]
                )
            else:
                initial_backblast_data[actions.BACKBLAST_MOLESKIN] = moleskin_block
            # initial_backblast_data[actions.BACKBLAST_MOLESKIN] = replace_slack_user_ids(
            #     initial_backblast_data[actions.BACKBLAST_MOLESKIN], client, logger, region_record
            # )
    elif event_id:
        event_record, attendance_records = event_preblast_query(event_id)
        initial_backblast_data = {
            actions.BACKBLAST_TITLE: event_record.event.name,
            actions.BACKBLAST_DATE: event_record.event.start_date.strftime("%Y-%m-%d"),
            actions.BACKBLAST_AO: event_record.org.slack_id,
            actions.BACKBLAST_Q: safe_get(
                [a.slack_user.slack_id for a in attendance_records if a.attendance.attendance_type_id == 2], 0
            ),
            actions.BACKBLAST_COQ: [
                a.slack_user.user_id for a in attendance_records if a.attendance.attendance_type_id == 3
            ],
            actions.BACKBLAST_PAX: [a.slack_user.slack_id for a in attendance_records],
        }
        parent_metadata["event_id"] = event_id
    else:
        initial_backblast_data = None

    backblast_form = copy.deepcopy(forms.BACKBLAST_FORM)
    backblast_form.set_initial_values(initial_backblast_data)
    backblast_form = add_custom_field_blocks(backblast_form, region_record)

    if backblast_method == "edit" or duplicate_check:
        og_ts = safe_get(body, "message", "ts") or safe_get(parent_metadata, "message_ts")
        is_duplicate = check_for_duplicate(
            q=safe_get(initial_backblast_data, actions.BACKBLAST_Q),
            date=safe_get(initial_backblast_data, actions.BACKBLAST_DATE),
            ao=safe_get(initial_backblast_data, actions.BACKBLAST_AO),
            region_record=region_record,
            logger=logger,
            og_ts=og_ts,
        )
        ao_id = safe_get(initial_backblast_data, actions.BACKBLAST_AO)
        ao_name = get_channel_name(ao_id, logger, client, region_record)
    else:
        is_duplicate = check_for_duplicate(
            q=user_id,
            date=datetime.now(pytz.timezone("US/Central")).date(),
            ao=channel_id,
            region_record=region_record,
            logger=logger,
        )
        ao_id = channel_id
        ao_name = channel_name

    logger.debug("is_duplicate is {}".format(is_duplicate))
    logger.debug("backblast_form is {}".format(backblast_form.blocks))
    if not is_duplicate:
        backblast_form.delete_block(actions.BACKBLAST_DUPLICATE_WARNING)

    # if backblast_method == "edit" or duplicate_check:
    #     backblast_form.set_initial_values(initial_backblast_data)

    if backblast_method == "edit":
        backblast_metadata = parent_metadata or {
            "channel_id": safe_get(body, "container", "channel_id"),
            "message_ts": safe_get(body, "container", "message_ts"),
            "files": safe_get(initial_backblast_data, actions.BACKBLAST_FILE) or [],
        }

        backblast_form.delete_block(actions.BACKBLAST_EMAIL_SEND)
        backblast_form.delete_block(actions.BACKBLAST_DESTINATION)
        callback_id = actions.BACKBLAST_EDIT_CALLBACK_ID
    else:
        logger.debug("ao_id is {}".format(ao_id))
        logger.debug("channel_id is {}".format(channel_id))
        backblast_form.set_options(
            {
                actions.BACKBLAST_DESTINATION: slack_orm.as_selector_options(
                    names=[f"The AO Channel (#{ao_name})", f"Current Channel (#{channel_name})"],
                    values=["The_AO", channel_id],
                )
            }
        )
        if not (region_record.email_enabled & region_record.email_option_show):
            backblast_form.delete_block(actions.BACKBLAST_EMAIL_SEND)
        backblast_metadata = None
        callback_id = actions.BACKBLAST_CALLBACK_ID

    # if backblast_method == "create":
    #     if (region_record.default_destination or "") == constants.CONFIG_DESTINATION_CURRENT["value"]:
    #         default_destination_id = channel_id
    #     elif (region_record.default_destination or "") == constants.CONFIG_DESTINATION_AO["value"]:
    #         default_destination_id = "The_AO"
    #     else:
    #         default_destination_id = None

    #     backblast_form.set_initial_values(
    #         {
    #             actions.BACKBLAST_Q: user_id,
    #             actions.BACKBLAST_DATE: datetime.now(pytz.timezone("US/Central")).strftime("%Y-%m-%d"),
    #             actions.BACKBLAST_DESTINATION: default_destination_id or "The_AO",
    #             actions.BACKBLAST_MOLESKIN: region_record.backblast_moleskin_template
    #             or constants.DEFAULT_BACKBLAST_MOLESKINE_TEMPLATE,
    #         }
    #     )
    #     if channel_id:
    #         backblast_form.set_initial_values({actions.BACKBLAST_AO: channel_id})
    # logger.debug(backblast_form.blocks)
    # logger.debug("backblast_form is {}".format(backblast_form.as_form_field()))

    if duplicate_check or update_view_id:
        backblast_form.update_modal(
            client=client,
            view_id=update_view_id,
            callback_id=callback_id,
            title_text="Backblast",
            parent_metadata=backblast_metadata,
        )
    else:
        backblast_form.post_modal(
            client=client,
            trigger_id=trigger_id,
            callback_id=callback_id,
            title_text="Backblast",
            parent_metadata=backblast_metadata,
        )


def handle_backblast_post(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    create_or_edit = "create" if safe_get(body, "view", "callback_id") == actions.BACKBLAST_CALLBACK_ID else "edit"

    backblast_form = copy.deepcopy(forms.BACKBLAST_FORM)
    backblast_form = add_custom_field_blocks(backblast_form, region_record)
    backblast_data: dict = backblast_form.get_selected_values(body)
    logger.debug(f"Backblast data: {backblast_data}")

    title = safe_get(backblast_data, actions.BACKBLAST_TITLE)
    the_date = safe_get(backblast_data, actions.BACKBLAST_DATE)
    the_ao = safe_get(backblast_data, actions.BACKBLAST_AO)
    the_q = safe_get(backblast_data, actions.BACKBLAST_Q)
    the_coq = safe_get(backblast_data, actions.BACKBLAST_COQ)
    pax = safe_get(backblast_data, actions.BACKBLAST_PAX)
    non_slack_pax = safe_get(backblast_data, actions.BACKBLAST_NONSLACK_PAX)
    fngs = safe_get(backblast_data, actions.BACKBLAST_FNGS)
    count = safe_get(backblast_data, actions.BACKBLAST_COUNT)
    moleskin = safe_get(backblast_data, actions.BACKBLAST_MOLESKIN)
    destination = safe_get(backblast_data, actions.BACKBLAST_DESTINATION)
    email_send = safe_get(backblast_data, actions.BACKBLAST_EMAIL_SEND)
    ao = safe_get(backblast_data, actions.BACKBLAST_AO)
    files = safe_get(backblast_data, actions.BACKBLAST_FILE) or []

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    file_list, file_send_list = upload_files_to_s3(files=files, user_id=user_id, logger=logger, client=client)

    user_records = None
    if region_record.paxminer_schema:
        user_records = DbManager.find_records(PaxminerUser, filters=[True], schema=region_record.paxminer_schema)

    chan = destination
    if chan == "The_AO":
        chan = the_ao

    if create_or_edit == "edit":
        message_metadata = json.loads(body["view"]["private_metadata"])
        message_channel = safe_get(message_metadata, "channel_id")
        message_ts = safe_get(message_metadata, "message_ts")
        file_list = safe_get(message_metadata, "files") if not file_list else file_list
    else:
        message_channel = chan
        message_ts = None

    auto_count = len(set([the_q] + (the_coq or []) + pax))
    pax_names_list = get_user_names(pax, logger, client, return_urls=False, user_records=user_records) or [""]
    # names, urls = get_user_names(
    #     [pax, the_coq or [], the_q], logger, client, return_urls=True, region_record=region_record
    # )
    pax_formatted = get_pax(pax)
    pax_full_list = [pax_formatted]
    fngs_formatted = fngs
    fng_count = 0
    if non_slack_pax:
        pax_full_list.append(non_slack_pax)
        pax_names_list.append(non_slack_pax)
        auto_count += non_slack_pax.count(",") + 1
    if fngs:
        pax_full_list.append(fngs)
        pax_names_list.append(fngs)
        fng_count = fngs.count(",") + 1
        fngs_formatted = str(fng_count) + " " + fngs
        auto_count += fngs.count(",") + 1
    pax_formatted = ", ".join(pax_full_list)
    pax_names = ", ".join(pax_names_list)

    if the_coq is None:
        the_coqs_formatted = ""
        the_coqs_names = ""
    else:
        the_coqs_formatted = get_pax(the_coq)
        the_coqs_full_list = [the_coqs_formatted]
        the_coqs_names_list = get_user_names(the_coq, logger, client, return_urls=False, user_records=user_records)
        the_coqs_formatted = ", " + ", ".join(the_coqs_full_list)
        the_coqs_names = ", " + ", ".join(the_coqs_names_list)

    # moleskin_formatted = parse_moleskin_users(moleskin, client, user_records)

    ao_name = get_channel_name(the_ao, logger, client, region_record)
    q_name, q_url = get_user_names([the_q], logger, client, return_urls=True, user_records=user_records)
    q_name = (q_name or [""])[0]
    q_url = q_url[0]

    count = count or auto_count

    post_msg = f"""*Backblast! {title}*
*DATE*: {the_date}
*AO*: <#{the_ao}>
*Q*: <@{the_q}>{the_coqs_formatted}
*PAX*: {pax_formatted}
*FNGs*: {fngs_formatted}
*COUNT*: {count}"""

    custom_fields = {}
    for field, value in backblast_data.items():
        if (field[: len(actions.CUSTOM_FIELD_PREFIX)] == actions.CUSTOM_FIELD_PREFIX) and value:
            post_msg += f"\n*{field[len(actions.CUSTOM_FIELD_PREFIX):]}*: {str(value)}"
            custom_fields[field[len(actions.CUSTOM_FIELD_PREFIX) :]] = value

    if file_list:
        custom_fields["files"] = file_list

    msg_block = {
        "type": "section",
        "text": {"type": "mrkdwn", "text": post_msg},
        "block_id": "msg_text",
    }

    # moleskin_block = {
    #     "type": "section",
    #     "text": {"type": "mrkdwn", "text": moleskin_formatted},
    #     "block_id": "moleskin_text",
    # }

    backblast_data.pop(actions.BACKBLAST_MOLESKIN, None)
    backblast_data[actions.BACKBLAST_FILE] = file_list

    backblast_data[actions.BACKBLAST_OP] = user_id

    edit_block = {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":pencil: Edit this backblast",
                    "emoji": True,
                },
                "value": "edit",
                "action_id": actions.BACKBLAST_EDIT_BUTTON,
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":heavy_plus_sign: New backblast",
                    "emoji": True,
                },
                "value": "new",
                "action_id": actions.BACKBLAST_NEW_BUTTON,
            },
        ],
        "block_id": actions.BACKBLAST_EDIT_BUTTON,
    }
    if region_record.strava_enabled:
        edit_block["elements"].append(
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":runner: Connect to Strava",
                    "emoji": True,
                },
                "value": "strava",
                "action_id": actions.BACKBLAST_STRAVA_BUTTON,
            }
        )

    blocks = [msg_block, moleskin]
    for file in file_list or []:
        blocks.append(
            slack_orm.ImageBlock(
                alt_text=title,
                image_url=file,
            ).as_form_field()
        )
    blocks.append(edit_block)

    moleskin_text = parse_rich_block(moleskin)
    moleskin_text_w_names = replace_user_channel_ids(moleskin_text, region_record, client, logger)

    if create_or_edit == "create":
        if region_record.paxminer_schema is None:
            text = (post_msg + "\n" + moleskin_text)[:1500]
            res = client.chat_postMessage(
                channel=chan,
                text=text,
                username=f"{q_name} (via Slackblast)",
                icon_url=q_url,
            )
        else:
            text = (f"{moleskin_text_w_names}\n\nUse the 'New Backblast' button to create a new backblast")[:1500]
            res = client.chat_postMessage(
                channel=chan,
                text=text,
                username=f"{q_name} (via Slackblast)",
                icon_url=q_url,
                blocks=blocks,
                metadata={"event_type": "backblast", "event_payload": backblast_data},
            )
        logger.debug("\nMessage posted to Slack! \n{}".format(post_msg))
        print(json.dumps({"event_type": "successful_slack_post", "team_name": region_record.workspace_name}))
        if (email_send and email_send == "yes") or (email_send is None and region_record.email_enabled == 1):
            moleskin_msg = moleskin_text_w_names

            if region_record.postie_format:
                subject = f"[{ao_name}] {title}"
                moleskin_msg += f"\n\nTags: {ao_name}, {pax_names}"
            else:
                subject = title

            email_msg = f"""Date: {the_date}
AO: {ao_name}
Q: {q_name} {the_coqs_names}
PAX: {pax_names}
FNGs: {fngs_formatted}
COUNT: {count}
{moleskin_msg}
            """

            try:
                # Decrypt password
                fernet = Fernet(os.environ[constants.PASSWORD_ENCRYPT_KEY].encode())
                email_password_decrypted = fernet.decrypt(region_record.email_password.encode()).decode()
                sendmail.send(
                    subject=subject,
                    body=email_msg,
                    email_server=region_record.email_server,
                    email_server_port=region_record.email_server_port,
                    email_user=region_record.email_user,
                    email_password=email_password_decrypted,
                    email_to=region_record.email_to,
                    attachments=file_send_list,
                )
                logger.debug("\nEmail Sent! \n{}".format(email_msg))
                print(
                    json.dumps(
                        {
                            "event_type": "successful_email_sent",
                            "team_name": region_record.workspace_name,
                        }
                    )
                )
            except Exception as sendmail_err:
                logger.error("Error with sendmail: {}".format(sendmail_err))
                logger.debug("\nEmail Sent! \n{}".format(email_msg))
                print(json.dumps({"event_type": "failed_email", "team_name": region_record.workspace_name}))

    elif create_or_edit == "edit":
        text = (f"{moleskin_text_w_names}\n\nUse the 'New Backblast' button to create a new backblast")[:1500]
        res = client.chat_update(
            channel=message_channel,
            ts=message_ts,
            text=text,
            username=f"{q_name} (via Slackblast)",
            icon_url=q_url,
            blocks=blocks,
            metadata={"event_type": "backblast", "event_payload": backblast_data},
        )
        logger.debug("\nBackblast updated in Slack! \n{}".format(post_msg))
        print(json.dumps({"event_type": "successful_slack_edit", "team_name": region_record.workspace_name}))

        if message_ts:
            DbManager.delete_records(
                cls=Backblast,
                schema=region_record.paxminer_schema,
                filters=[Backblast.timestamp == message_ts],
            )
            DbManager.delete_records(
                cls=Attendance,
                schema=region_record.paxminer_schema,
                filters=[Attendance.timestamp == message_ts],
            )
        logger.debug("\nBackblast deleted from database! \n{}".format(post_msg))
        print(json.dumps({"event_type": "successful_db_delete", "team_name": region_record.workspace_name}))

    res_link = client.chat_getPermalink(channel=chan or message_channel, message_ts=res["ts"])

    if region_record.paxminer_schema is not None:
        backblast_parsed = f"""Backblast! {title}
Date: {the_date}
AO: {ao_name}
Q: {q_name} {the_coqs_names}
PAX: {pax_names}
FNGs: {fngs_formatted}
COUNT: {count}
{moleskin_text_w_names}
"""
        try:
            DbManager.create_record(
                schema=region_record.paxminer_schema,
                record=Backblast(
                    timestamp=message_ts or res["ts"],
                    ts_edited=safe_get(res, "message", "edited", "ts"),
                    ao_id=ao or chan,
                    bd_date=the_date,
                    q_user_id=the_q,
                    coq_user_id=the_coq[0] if the_coq else None,
                    pax_count=count,
                    backblast=f"{post_msg}\n{moleskin_text}".replace("*", ""),
                    backblast_parsed=backblast_parsed,
                    fngs=fngs_formatted if fngs else "None listed",
                    fng_count=fng_count,
                    json=custom_fields,
                ),
            )

            attendance_records = []
            for pax_id in list(set(pax) | set(the_coq or []) | {the_q}):
                attendance_records.append(
                    Attendance(
                        timestamp=message_ts or res["ts"],
                        ts_edited=safe_get(res, "message", "edited", "ts"),
                        user_id=pax_id,
                        ao_id=ao or chan,
                        date=the_date,
                        q_user_id=the_q,
                    )
                )

            DbManager.create_records(schema=region_record.paxminer_schema, records=attendance_records)
            print(
                json.dumps(
                    {
                        "event_type": "successful_db_insert",
                        "team_name": region_record.workspace_name,
                    }
                )
            )

            paxminer_log_channel = get_channel_id(name="paxminer_logs", client=client, logger=logger)
            if paxminer_log_channel:
                import_or_edit = "imported" if create_or_edit == "create" else "edited"
                client.chat_postMessage(
                    channel=paxminer_log_channel,
                    text=f"Backblast successfully {import_or_edit} for AO: <#{ao or chan}> Date: {the_date} Q: {q_name}"
                    f"\nLink: {res_link['permalink']}",
                )
        except Exception as e:
            logger.error("Error saving backblast to database: {}".format(e))
            client.chat_postMessage(
                channel=context["user_id"],
                text="WARNING: The backblast you just posted was not saved to the database. There is already a "
                "backblast for this AO and Q on this date. Please edit the backblast using the `Edit this backblast`"
                "button. Thanks!",
            )
            print(json.dumps({"event_type": "failed_db_insert", "team_name": region_record.workspace_name}))

    for file in file_send_list:
        try:
            os.remove(file["filepath"])
        except Exception as e:
            logger.error(f"Error removing file: {e}")


def handle_backblast_edit_button(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")

    backblast_data = safe_get(body, "message", "metadata", "event_payload") or json.loads(
        safe_get(body, "actions", 0, "value") or "{}"
    )

    if region_record.editing_locked == 1:
        user_info_dict = client.users_info(user=user_id)
        user_admin: bool = user_info_dict["user"]["is_admin"]
        allow_edit: bool = (
            user_admin
            or (user_id == backblast_data[actions.BACKBLAST_Q])
            or (user_id in backblast_data[actions.BACKBLAST_COQ] or [])
            or (user_id in backblast_data[actions.BACKBLAST_OP])
        )
    else:
        allow_edit = True

    if allow_edit:
        build_backblast_form_new(
            body=body,
            client=client,
            logger=logger,
            context=context,
            region_record=region_record,
        )
    else:
        client.chat_postEphemeral(
            text="Editing this backblast is only allowed for the Q(s), the original poster, or your local Slack admins."
            "Please contact one of them to make changes.",
            channel=channel_id,
            user=user_id,
        )
