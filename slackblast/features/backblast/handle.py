import copy
import json
import os
from logging import Logger

import boto3
import requests
from cryptography.fernet import Fernet
from PIL import Image
from pillow_heif import register_heif_opener
from slack_sdk.web import WebClient

from features.backblast import add_custom_field_blocks, build, ui
from utilities import constants, sendmail
from utilities.database import DbManager
from utilities.database.orm import Attendance, Backblast, PaxminerUser, Region
from utilities.helper_functions import (
    get_channel_id,
    get_channel_name,
    get_pax,
    get_user_names,
    parse_rich_block,
    replace_user_channel_ids,
    safe_get,
)
from utilities.slack import actions
from utilities.slack import orm as slack_orm

register_heif_opener()


def handle_backblast_post(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    create_or_edit = "create" if safe_get(body, "view", "callback_id") == actions.BACKBLAST_CALLBACK_ID else "edit"

    backblast_form = copy.deepcopy(ui.BACKBLAST_FORM)
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

    file_list = []
    file_send_list = []
    for file in files or []:
        try:
            r = requests.get(file["url_private_download"], headers={"Authorization": f"Bearer {client.token}"})
            r.raise_for_status()

            file_name = f"{file['id']}.{file['filetype']}"
            file_path = f"/tmp/{file_name}"
            file_mimetype = file["mimetype"]

            with open(file_path, "wb") as f:
                f.write(r.content)

            if file["filetype"] == "heic":
                heic_img = Image.open(file_path)
                x, y = heic_img.size
                coeff = min(constants.MAX_HEIC_SIZE / max(x, y), 1)
                heic_img = heic_img.resize((int(x * coeff), int(y * coeff)))
                heic_img.save(file_path.replace(".heic", ".png"), quality=95, optimize=True, format="PNG")
                os.remove(file_path)

                file_path = file_path.replace(".heic", ".png")
                file_name = file_name.replace(".heic", ".png")
                file_mimetype = "image/png"

            # read first line of file to determine if it's an image
            with open(file_path, "rb") as f:
                try:
                    first_line = f.readline().decode("utf-8")
                except Exception as e:
                    logger.info(f"Error reading photo as text: {e}")
                    first_line = ""
            if first_line[:9] == "<!DOCTYPE":
                logger.debug(f"File {file_name} is not an image, skipping")
                msg = "To enable boybands, you will need to reinstall Slackblast with some new permissions."
                msg += " To to this, simply use this link: "
                msg += "https://n1tbdh3ak9.execute-api.us-east-2.amazonaws.com/Prod/slack/install."
                msg += " You can edit your backblast and upload a boyband once this is complete."
                client.chat_postMessage(
                    text=msg,
                    channel=user_id,
                )
            else:
                if constants.LOCAL_DEVELOPMENT:
                    s3_client = boto3.client(
                        "s3",
                        aws_access_key_id=os.environ[constants.AWS_ACCESS_KEY_ID],
                        aws_secret_access_key=os.environ[constants.AWS_SECRET_ACCESS_KEY],
                    )
                else:
                    s3_client = boto3.client("s3")
                with open(file_path, "rb") as f:
                    s3_client.upload_fileobj(
                        f, "slackblast-images", file_name, ExtraArgs={"ContentType": file_mimetype}
                    )
                file_list.append(f"https://slackblast-images.s3.amazonaws.com/{file_name}")
                file_send_list.append(
                    {
                        "filepath": file_path,
                        "meta": {
                            "filename": file_name,
                            "maintype": file_mimetype.split("/")[0],
                            "subtype": file_mimetype.split("/")[1],
                        },
                    }
                )
        except Exception as e:
            logger.error(f"Error uploading file: {e}")

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")

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
            res = client.chat_postMessage(
                channel=chan,
                text=post_msg + "\n" + moleskin_text,
                username=f"{q_name} (via Slackblast)",
                icon_url=q_url,
            )
        else:
            res = client.chat_postMessage(
                channel=chan,
                text=f"{moleskin_text_w_names}\n\nUse the 'New Backblast' button to create a new backblast",
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
        res = client.chat_update(
            channel=message_channel,
            ts=message_ts,
            text=f"{moleskin_text_w_names}\n\nUse the 'New Backblast' button to create a new backblast",
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
                    backblast=f"{post_msg}\n{moleskin_text}".replace(
                        "*", ""
                    ),  # here's where to replace with name versions
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

    user_info_dict = client.users_info(user=user_id)
    user_admin: bool = user_info_dict["user"]["is_admin"]
    allow_edit: bool = (
        (region_record.editing_locked == 0)
        or user_admin
        or (user_id == backblast_data[actions.BACKBLAST_Q])
        or (user_id in backblast_data[actions.BACKBLAST_COQ] or [])
        or (user_id in backblast_data[actions.BACKBLAST_OP])
    )

    if allow_edit:
        build.build_backblast_form(
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
