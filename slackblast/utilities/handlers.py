import json
import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from utilities import constants, sendmail

from utilities.helper_functions import (
    get_channel_id,
    safe_get,
    get_user_names,
    get_pax,
    parse_moleskin_users,
    get_channel_name,
)
from utilities.slack import actions
from utilities.database.orm import Attendance, Backblast, Region
from utilities.database import DbManager
from cryptography.fernet import Fernet


def handle_backblast_post(
    ack, body, logger, client, context, backblast_data, create_or_edit: str
) -> str:
    ack()

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

    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    region_record: Region = DbManager.get_record(Region, id=context["team_id"])

    chan = destination
    if chan == "The_AO":
        chan = the_ao

    if create_or_edit == "edit":
        message_metadata = body["view"]["blocks"][-1]["elements"][0]["text"]
        message_channel, message_ts = message_metadata.split("|")
    else:
        message_channel = chan
        message_ts = None

    auto_count = len(set(list([the_q] + (the_coq or []) + pax)))
    pax_names_list = get_user_names(pax, logger, client, return_urls=False) or [""]
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

    if the_coq == None:
        the_coqs_formatted = ""
        the_coqs_names = ""
    else:
        the_coqs_formatted = get_pax(the_coq)
        the_coqs_full_list = [the_coqs_formatted]
        the_coqs_names_list = get_user_names(the_coq, logger, client, return_urls=False)
        the_coqs_formatted = ", " + ", ".join(the_coqs_full_list)
        the_coqs_names = ", " + ", ".join(the_coqs_names_list)

    moleskin_formatted = parse_moleskin_users(moleskin, client)

    ao_name = get_channel_name(the_ao, logger, client)
    q_name, q_url = get_user_names([the_q], logger, client, return_urls=True)
    q_name = (q_name or [""])[0]
    q_url = q_url[0]

    count = count or auto_count

    post_msg = f"""*Backblast! {title}*
*DATE*: {the_date}
*AO*: <#{the_ao}>
*Q*: <@{the_q}>{the_coqs_formatted}
*PAX*: {pax_formatted}
*FNGs*: {fngs_formatted}
*COUNT*: {count}
    """

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

    ignore = backblast_data.pop(actions.BACKBLAST_MOLESKIN, None)

    backblast_data[actions.BACKBLAST_OP] = user_id

    edit_block = {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Edit this backblast", "emoji": True},
                "value": json.dumps(backblast_data),
                "action_id": actions.BACKBLAST_EDIT_BUTTON,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "New backblast", "emoji": True},
                "value": "new",
                "action_id": actions.BACKBLAST_NEW_BUTTON,
            },
        ],
        "block_id": actions.BACKBLAST_EDIT_BUTTON,
    }

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
                text="Use 'New Backblast' button to create a new backblast",
                username=f"{q_name} (via Slackblast)",
                icon_url=q_url,
                blocks=[msg_block, moleskin_block, edit_block],
            )
        logger.info("\nMessage posted to Slack! \n{}".format(post_msg))

        if (email_send and email_send == "yes") or (
            email_send is None and region_record.email_enabled == 1
        ):
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
                email_password_decrypted = fernet.decrypt(
                    region_record.email_password.encode()
                ).decode()
                sendmail.send(
                    subject=subject,
                    body=email_msg,
                    email_server=region_record.email_server,
                    email_server_port=region_record.email_server_port,
                    email_user=region_record.email_user,
                    email_password=email_password_decrypted,
                    email_to=region_record.email_to,
                )
                logger.info("\nEmail Sent! \n{}".format(email_msg))
            except Exception as sendmail_err:
                logger.error("Error with sendmail: {}".format(sendmail_err))
                logger.info("\nEmail Sent! \n{}".format(email_msg))

    elif create_or_edit == "edit":
        res = client.chat_update(
            channel=message_channel,
            ts=message_ts,
            text="Use 'New Backblast' button to create a new backblast",
            username=f"{q_name} (via Slackblast)",
            icon_url=q_url,
            blocks=[msg_block, moleskin_block, edit_block],
        )
        logger.info("\nBackblast updated in Slack! \n{}".format(post_msg))

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
        logger.info("\nBackblast deleted from database! \n{}".format(post_msg))

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

            DbManager.create_records(
                schema=region_record.paxminer_schema, records=attendance_records
            )

            paxminer_log_channel = get_channel_id(
                name="paxminer_logs", client=client, logger=logger
            )
            if paxminer_log_channel:
                import_or_edit = "imported" if create_or_edit == "create" else "edited"
                client.chat_postMessage(
                    channel=paxminer_log_channel,
                    text=f"Backblast successfully {import_or_edit} for AO: <#{ao or chan}> Date: {the_date} Q: {q_name}\nLink: {res_link['permalink']}",
                )
        except Exception as e:
            logger.error("Error saving backblast to database: {}".format(e))
            client.chat_postMessage(
                channel=context["user_id"],
                text=f"WARNING: The backblast you just posted was not saved to the database. There is already a backblast for this AO and Q on this date. Please edit the backblast using the `Edit this backblast` button. Thanks!",
            )

    if create_or_edit == "create" and (
        (email_send and email_send == "yes")
        or (email_send is None and region_record.email_enabled == 1)
    ):
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
            email_password_decrypted = fernet.decrypt(
                region_record.email_password.encode()
            ).decode()
            sendmail.send(
                subject=subject,
                body=email_msg,
                email_server=region_record.email_server,
                email_server_port=region_record.email_server_port,
                email_user=region_record.email_user,
                email_password=email_password_decrypted,
                email_to=region_record.email_to,
            )
            logger.info("\nEmail Sent! \n{}".format(email_msg))
        except Exception as sendmail_err:
            logger.error("Error with sendmail: {}".format(sendmail_err))
            logger.info("\nEmail Sent! \n{}".format(email_msg))


def handle_preblast_post(ack, body, logger, client, context, preblast_data) -> str:
    ack()

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

    chan = destination
    if chan == "The_AO":
        chan = the_ao

    q_name, q_url = get_user_names([the_q], logger, client, return_urls=True)
    q_name = (q_name or [""])[0]
    q_url = q_url[0]

    header_msg = f"*Preblast: " + title + "*"
    date_msg = f"*Date*: " + the_date
    time_msg = f"*Time*: " + the_time
    ao_msg = f"*Where*: <#" + the_ao + ">"
    q_msg = f"*Q*: <@" + the_q + ">"  # + the_coqs_formatted

    body_list = [header_msg, date_msg, time_msg, ao_msg, q_msg]
    if the_why:
        body_list.append(f"*Why*: " + the_why)
    if coupons:
        body_list.append(f"*Coupons*: " + coupons)
    if fngs:
        body_list.append(f"*FNGs*: " + fngs)
    if moleskin:
        body_list.append(moleskin)

    msg = "\n".join(body_list)
    client.chat_postMessage(
        channel=chan, text=msg, username=f"{q_name} (via Slackblast)", icon_url=q_url
    )
    logger.info("\nMessage posted to Slack! \n{}".format(msg))


def handle_config_post(ack, body, logger, client, context, config_data) -> str:
    ack()

    fields = {
        # Region.paxminer_schema: paxminer_db,
        Region.email_enabled: 1
        if safe_get(config_data, actions.CONFIG_EMAIL_ENABLE) == "enable"
        else 0,
        Region.editing_locked: 1
        if safe_get(config_data, actions.CONFIG_EDITING_LOCKED) == "yes"
        else 0,
        Region.default_destination: safe_get(config_data, actions.CONFIG_DEFAULT_DESTINATION),
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
                Region.email_option_show: 1
                if safe_get(config_data, actions.CONFIG_EMAIL_SHOW_OPTION) == "yes"
                else 0,
                Region.email_server: safe_get(config_data, actions.CONFIG_EMAIL_SERVER),
                Region.email_server_port: safe_get(config_data, actions.CONFIG_EMAIL_PORT),
                Region.email_user: safe_get(config_data, actions.CONFIG_EMAIL_FROM),
                Region.email_to: safe_get(config_data, actions.CONFIG_EMAIL_TO),
                Region.email_password: email_password_encrypted,
                Region.postie_format: 1
                if safe_get(config_data, actions.CONFIG_POSTIE_ENABLE) == "yes"
                else 0,
            }
        )

    DbManager.update_record(
        cls=Region,
        id=context["team_id"],
        fields=fields,
    )
