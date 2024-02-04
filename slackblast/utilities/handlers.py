import copy
import json
from logging import Logger
import os
from utilities import constants, sendmail, builders
from utilities.helper_functions import (
    get_channel_id,
    safe_get,
    get_user_names,
    get_pax,
    parse_moleskin_users,
    get_channel_name,
    update_local_region_records,
)
from utilities.slack import actions, forms, orm
from utilities.database.orm import Attendance, Backblast, PaxminerUser, Region
from utilities.database import DbManager
from cryptography.fernet import Fernet
from slack_sdk.web import WebClient
import requests
import boto3

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def handle_backblast_post(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    create_or_edit = "create" if safe_get(body, "view", "callback_id") == actions.BACKBLAST_CALLBACK_ID else "edit"

    backblast_form = copy.deepcopy(forms.BACKBLAST_FORM)
    backblast_form = builders.add_custom_field_blocks(backblast_form, region_record)
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
            with open(file_path, "wb") as f:
                f.write(r.content)

            # read first line of file to determine if it's an image
            with open(file_path, "rb") as f:
                try:
                    first_line = f.readline().decode("utf-8")
                except Exception as e:
                    logger.info(f"Error reading photo as text: {e}")
                    first_line = ""
            if first_line[:9] == "<!DOCTYPE":
                logger.debug(f"File {file_name} is not an image, skipping")
                client.chat_postMessage(
                    text="To enable boybands, you will need to reinstall Slackblast with some new permissions. To to this, simply use this link: https://n1tbdh3ak9.execute-api.us-east-2.amazonaws.com/Prod/slack/install. You can edit your backblast and upload a boyband once this is complete.",
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
                        f, "slackblast-images", file_name, ExtraArgs={"ContentType": file["mimetype"]}
                    )
                file_list.append(f"https://slackblast-images.s3.amazonaws.com/{file_name}")
                file_send_list.append(
                    {
                        "filepath": file_path,
                        "meta": {
                            "filename": file_name,
                            "maintype": file["mimetype"].split("/")[0],
                            "subtype": file["mimetype"].split("/")[1],
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

    auto_count = len(set(list([the_q] + (the_coq or []) + pax)))
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

    moleskin_formatted = parse_moleskin_users(moleskin, client, user_records)

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

    moleskin_block = {
        "type": "section",
        "text": {"type": "mrkdwn", "text": moleskin_formatted},
        "block_id": "moleskin_text",
    }

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
                "value": json.dumps(backblast_data),
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

    blocks = [msg_block, moleskin_block]
    for file in file_list or []:
        blocks.append(
            orm.ImageBlock(
                alt_text=title,
                image_url=file,
            ).as_form_field()
        )
    blocks.append(edit_block)

    if create_or_edit == "create":
        if region_record.paxminer_schema is None:
            res = client.chat_postMessage(
                channel=chan,
                text=post_msg + "\n" + moleskin_formatted,
                username=f"{q_name} (via Slackblast)",
                icon_url=q_url,
            )
        else:
            res = client.chat_postMessage(
                channel=chan,
                text=f"{moleskin_formatted}\n\nUse the 'New Backblast' button to create a new backblast",
                username=f"{q_name} (via Slackblast)",
                icon_url=q_url,
                blocks=blocks,
            )
        logger.debug("\nMessage posted to Slack! \n{}".format(post_msg))
        print(json.dumps({"event_type": "successful_slack_post", "team_name": region_record.workspace_name}))
        if (email_send and email_send == "yes") or (email_send is None and region_record.email_enabled == 1):
            moleskin_msg = moleskin.replace("*", "")

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
            text=f"{moleskin_formatted}\n\nUse the 'New Backblast' button to create a new backblast",
            username=f"{q_name} (via Slackblast)",
            icon_url=q_url,
            blocks=blocks,
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
                    backblast=f"{post_msg}\n{moleskin_formatted}".replace("*", ""),
                    fngs=fngs_formatted if fngs else "None listed",
                    fng_count=fng_count,
                    json=custom_fields,
                ),
            )

            attendance_records = []
            for pax_id in list(set(pax) | set(the_coq or []) | set([the_q])):
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


def handle_preblast_post(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    create_or_edit = "create" if safe_get(body, "view", "callback_id") == actions.PREBLAST_CALLBACK_ID else "edit"

    preblast_data = forms.PREBLAST_FORM.get_selected_values(body)
    preblast_data[actions.PREBLAST_OP] = safe_get(body, "user_id") or safe_get(body, "user", "id")

    title = safe_get(preblast_data, actions.PREBLAST_TITLE)
    the_date = safe_get(preblast_data, actions.PREBLAST_DATE)
    the_time = safe_get(preblast_data, actions.PREBLAST_TIME)
    the_ao = safe_get(preblast_data, actions.PREBLAST_AO)
    the_q = safe_get(preblast_data, actions.PREBLAST_Q)
    the_why = safe_get(preblast_data, actions.PREBLAST_WHY)
    fngs = safe_get(preblast_data, actions.PREBLAST_FNGS)
    coupons = safe_get(preblast_data, actions.PREBLAST_COUPONS)
    moleskin = safe_get(preblast_data, actions.PREBLAST_MOLESKIN)
    destination = safe_get(preblast_data, actions.PREBLAST_DESTINATION)

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
    else:
        message_channel = chan
        message_ts = None

    q_name, q_url = get_user_names([the_q], logger, client, return_urls=True, user_records=user_records)
    q_name = (q_name or [""])[0]
    q_url = q_url[0]

    header_msg = f"*Preblast: {title}*"
    date_msg = f"*Date*: {the_date}"
    time_msg = f"*Time*: {the_time}"
    ao_msg = f"*Where*: <#{the_ao}>"
    q_msg = f"*Q*: <@{the_q}>"  # + the_coqs_formatted

    body_list = [header_msg, date_msg, time_msg, ao_msg, q_msg]
    if the_why:
        body_list.append(f"*Why*: {the_why}")
    if coupons:
        body_list.append(f"*Coupons*: {coupons}")
    if fngs:
        body_list.append(f"*FNGs*: {fngs}")
    if moleskin:
        body_list.append(moleskin)

    msg = "\n".join(body_list)

    msg_block = {
        "type": "section",
        "text": {"type": "mrkdwn", "text": msg},
        "block_id": "msg_text",
    }
    action_block = {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":pencil: Edit this preblast",
                    "emoji": True,
                },
                "value": json.dumps(preblast_data),
                "action_id": actions.PREBLAST_EDIT_BUTTON,
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":heavy_plus_sign: New preblast",
                    "emoji": True,
                },
                "value": "new",
                "action_id": actions.PREBLAST_NEW_BUTTON,
            },
        ],
        "block_id": actions.PREBLAST_EDIT_BUTTON,
    }
    if create_or_edit == "create":
        client.chat_postMessage(
            channel=chan,
            text=msg,
            username=f"{q_name} (via Slackblast)",
            icon_url=q_url,
            blocks=[msg_block, action_block],
        )
        logger.debug("\nPreblast posted to Slack! \n{}".format(msg))
        print(json.dumps({"event_type": "successful_preblast_create", "team_name": region_record.workspace_name}))
    elif create_or_edit == "edit":
        client.chat_update(
            channel=message_channel,
            ts=message_ts,
            text=msg,
            username=f"{q_name} (via Slackblast)",
            icon_url=q_url,
            blocks=[msg_block, action_block],
        )
        logger.debug("\nPreblast updated in Slack! \n{}".format(msg))
        print(json.dumps({"event_type": "successful_preblast_edit", "team_name": region_record.workspace_name}))


def handle_config_post(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    config_data = forms.CONFIG_FORM.get_selected_values(body)

    fields = {
        # Region.paxminer_schema: paxminer_db,
        Region.email_enabled: 1 if safe_get(config_data, actions.CONFIG_EMAIL_ENABLE) == "enable" else 0,
        Region.editing_locked: 1 if safe_get(config_data, actions.CONFIG_EDITING_LOCKED) == "yes" else 0,
        Region.default_destination: safe_get(config_data, actions.CONFIG_DEFAULT_DESTINATION),
        Region.backblast_moleskin_template: safe_get(config_data, actions.CONFIG_BACKBLAST_MOLESKINE_TEMPLATE) or "",
        Region.preblast_moleskin_template: safe_get(config_data, actions.CONFIG_PREBLAST_MOLESKINE_TEMPLATE) or "",
        Region.strava_enabled: 1 if safe_get(config_data, actions.CONFIG_ENABLE_STRAVA) == "enable" else 0,
    }
    if safe_get(config_data, actions.CONFIG_EMAIL_ENABLE) == "enable":
        fernet = Fernet(os.environ[constants.PASSWORD_ENCRYPT_KEY].encode())
        email_password_decrypted = safe_get(config_data, actions.CONFIG_EMAIL_PASSWORD)
        if email_password_decrypted:
            email_password_encrypted = fernet.encrypt(
                safe_get(config_data, actions.CONFIG_EMAIL_PASSWORD).encode()
            ).decode()
        else:
            email_password_encrypted = None
        fields.update(
            {
                Region.email_option_show: 1 if safe_get(config_data, actions.CONFIG_EMAIL_SHOW_OPTION) == "yes" else 0,
                Region.email_server: safe_get(config_data, actions.CONFIG_EMAIL_SERVER),
                Region.email_server_port: safe_get(config_data, actions.CONFIG_EMAIL_PORT),
                Region.email_user: safe_get(config_data, actions.CONFIG_EMAIL_FROM),
                Region.email_to: safe_get(config_data, actions.CONFIG_EMAIL_TO),
                Region.email_password: email_password_encrypted,
                Region.postie_format: 1 if safe_get(config_data, actions.CONFIG_POSTIE_ENABLE) == "yes" else 0,
            }
        )

    DbManager.update_record(
        cls=Region,
        id=context["team_id"],
        fields=fields,
    )
    update_local_region_records()
    print(json.dumps({"event_type": "successful_config_update", "team_name": region_record.workspace_name}))


def handle_welcome_message_config_post(
    body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region
):
    welcome_config_data = forms.WELCOME_MESSAGE_CONFIG_FORM.get_selected_values(body)

    fields = {
        Region.welcome_dm_enable: 1 if safe_get(welcome_config_data, actions.WELCOME_DM_ENABLE) == "enable" else 0,
        Region.welcome_dm_template: safe_get(welcome_config_data, actions.WELCOME_DM_TEMPLATE) or "",
        Region.welcome_channel_enable: 1
        if safe_get(welcome_config_data, actions.WELCOME_CHANNEL_ENABLE) == "enable"
        else 0,
        Region.welcome_channel: safe_get(welcome_config_data, actions.WELCOME_CHANNEL) or "",
    }

    DbManager.update_record(
        cls=Region,
        id=context["team_id"],
        fields=fields,
    )
    update_local_region_records()
    print(json.dumps({"event_type": "successful_config_update", "team_name": region_record.workspace_name}))


def handle_custom_field_add(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    config_data = forms.CUSTOM_FIELD_ADD_EDIT_FORM.get_selected_values(body)

    custom_field_name = safe_get(config_data, actions.CUSTOM_FIELD_ADD_NAME)
    custom_field_type = safe_get(config_data, actions.CUSTOM_FIELD_ADD_TYPE)
    custom_field_options = safe_get(config_data, actions.CUSTOM_FIELD_ADD_OPTIONS)

    custom_fields = region_record.custom_fields or {}
    custom_fields[custom_field_name] = {
        "name": custom_field_name,
        "type": custom_field_type,
        "options": custom_field_options.split(",") if custom_field_options else [],
        "enabled": True,
    }

    DbManager.update_record(cls=Region, id=region_record.team_id, fields={Region.custom_fields: custom_fields})
    update_local_region_records()

    print(
        json.dumps(
            {
                "event_type": "successful_custom_field_add_edit",
                "team_name": region_record.workspace_name,
            }
        )
    )

    previous_view_id = safe_get(body, "view", "previous_view_id")
    builders.build_custom_field_menu(body, client, logger, context, region_record, update_view_id=previous_view_id)


def handle_custom_field_menu(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    custom_fields = region_record.custom_fields or {}

    selected_values: dict = safe_get(body, "view", "state", "values")

    for key, value in selected_values.items():
        if key[: len(actions.CUSTOM_FIELD_ENABLE)] == actions.CUSTOM_FIELD_ENABLE:
            custom_fields[key[len(actions.CUSTOM_FIELD_ENABLE) + 1 :]]["enabled"] = (
                value[key]["selected_option"]["value"] == "enable"
            )

    DbManager.update_record(cls=Region, id=region_record.team_id, fields={Region.custom_fields: custom_fields})
    update_local_region_records()
