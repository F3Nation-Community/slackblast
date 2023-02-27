from utilities import sendmail, constants
from utilities.database.orm import Region
from utilities.database import DbManager
from datetime import datetime
from utilities.slack import actions
from utilities.constants import LOCAL_DEVELOPMENT
import os
import sys
from slack_bolt.adapter.aws_lambda.lambda_s3_oauth_flow import LambdaS3OAuthFlow
from slack_bolt.oauth.oauth_settings import OAuthSettings
import re
from cryptography.fernet import Fernet
from slack_sdk.web import WebClient
import json

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))


def get_oauth_flow():
    if LOCAL_DEVELOPMENT:
        return None
    else:
        return LambdaS3OAuthFlow(
            oauth_state_bucket_name=os.environ[constants.SLACK_STATE_S3_BUCKET_NAME],
            installation_bucket_name=os.environ[constants.SLACK_INSTALLATION_S3_BUCKET_NAME],
            settings=OAuthSettings(
                client_id=os.environ[constants.SLACK_CLIENT_ID],
                client_secret=os.environ[constants.SLACK_CLIENT_SECRET],
                scopes=os.environ[constants.SLACK_SCOPES].split(","),
            ),
        )


def safe_get(data, *keys):
    try:
        result = data
        for k in keys:
            if result.get(k):
                result = result[k]
            else:
                return None
        return result
    except KeyError:
        return None


def get_channel_id_and_name(body, logger):
    # returns channel_iid, channel_name if it exists as an escaped parameter of slashcommand
    user_id = body.get("user_id")
    # Get "text" value which is everything after the /slash-command
    # e.g. /slackblast #our-aggregate-backblast-channel
    # then text would be "#our-aggregate-backblast-channel" if /slash command is not encoding
    # but encoding needs to be checked so it will be "<#C01V75UFE56|our-aggregate-backblast-channel>" instead
    channel_name = body.get("text") or ""
    channel_id = ""
    try:
        channel_id = channel_name.split("|")[0].split("#")[1]
        channel_name = channel_name.split("|")[1].split(">")[0]
    except IndexError as ierr:
        logger.error("Bad user input - cannot parse channel id")
    except Exception as error:
        logger.error("User did not pass in any input")
    return channel_id, channel_name


def get_channel_name(id, logger, client):
    channel_info_dict = client.conversations_info(channel=id)
    channel_name = safe_get(channel_info_dict, "channel", "name") or None
    logger.info("channel_name is {}".format(channel_name))
    return channel_name


def get_user_names(array_of_user_ids, logger, client, return_urls=False):
    names = []
    urls = []

    for user_id in array_of_user_ids:
        user_info_dict = client.users_info(user=user_id)
        user_name = (
            safe_get(user_info_dict, "user", "profile", "display_name")
            or safe_get(user_info_dict, "user", "profile", "real_name")
            or None
        )
        if user_name:
            names.append(user_name)
        logger.info("user_name is {}".format(user_name))

        user_icon_url = user_info_dict["user"]["profile"]["image_192"]
        urls.append(user_icon_url)
    logger.info("names are {}".format(names))

    if return_urls:
        return names, urls
    else:
        return names


def get_user_ids(user_names, client):
    members = client.users_list()["members"]

    member_list = {}
    for member in members:
        member_dict = member["profile"]
        member_dict.update({"id": member["id"]})
        if member_dict["display_name"] == "":
            member_dict["display_name"] = member_dict["real_name"]
        member_dict["display_name"] = member_dict["display_name"].lower()
        member_dict["display_name"] = re.sub(
            "\s\(([\s\S]*?\))", "", member_dict["display_name"]
        ).replace(" ", "_")
        member_list[member_dict["display_name"]] = member_dict["id"]

    user_ids = []
    for user_name in user_names:
        user_name_fmt = user_name.lower()
        user = safe_get(member_list, user_name_fmt)
        if user:
            user = f"<@{user}>"
        else:
            user = user_name

        user_ids.append(user)

    return user_ids


def parse_moleskin_users(msg, client):
    pattern = "@([A-Za-z0-9-_']+)"
    user_ids = get_user_ids(re.findall(pattern, msg), client)

    msg2 = re.sub(pattern, "{}", msg).format(*user_ids)
    return msg2


def get_pax(pax):
    p = ""
    for x in pax:
        p += "<@" + x + "> "
    return p


def handle_backblast_post(ack, body, logger, client, context, backblast_data) -> str:
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
    moleskine = safe_get(backblast_data, actions.BACKBLAST_MOLESKIN)
    destination = safe_get(backblast_data, actions.BACKBLAST_DESTINATION)
    email_send = safe_get(backblast_data, actions.BACKBLAST_EMAIL_SEND)

    region_record: Region = DbManager.get_record(Region, id=context["team_id"])

    pax_names_list = get_user_names(pax, logger, client, return_urls=False) or [""]
    pax_formatted = get_pax(pax)
    pax_full_list = [pax_formatted]
    fngs_formatted = fngs
    if non_slack_pax != "None":
        pax_full_list.append(non_slack_pax)
        pax_names_list.append(non_slack_pax)
    if fngs != "None":
        pax_full_list.append(fngs)
        pax_names_list.append(fngs)
        fngs_formatted = str(fngs.count(",") + 1) + " " + fngs
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

    moleskine_formatted = parse_moleskin_users(moleskine, client)

    chan = destination
    if chan == "The_AO":
        chan = the_ao

    ao_name = get_channel_name(the_ao, logger, client)
    q_name, q_url = get_user_names([the_q], logger, client, return_urls=True)
    q_name = (q_name or [""])[0]
    q_url = q_url[0]

    post_msg = f"""
*Slackblast*:
*{title}*
*DATE*: {the_date}
*AO*: <#{the_ao}>
*Q*: <@{the_q}>{the_coqs_formatted}
*PAX*: {pax_formatted}
*FNGS*: {fngs_formatted}
*COUNT*: {count}
{moleskine_formatted}
    """

    msg_block = {
        "type": "section",
        "text": {"type": "mrkdwn", "text": post_msg},
        "block_id": "msg_text",
    }

    edit_block = {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Edit this backblast", "emoji": True},
                "value": json.dumps(backblast_data),
                "action_id": actions.BACKBLAST_EDIT_BUTTON,
            }
        ],
        "block_id": actions.BACKBLAST_EDIT_BUTTON,
    }

    if (email_send and email_send == "yes") or (
        email_send is None and region_record.email_enabled == 1
    ):
        moleskine_msg = moleskine.replace("*", "")

        if region_record.postie_format:
            subject = f"[{ao_name}] {title}"
            moleskine_msg += f"\n\nTags: {ao_name}, {pax_names}"
        else:
            subject = title

        email_msg = f"""
Date: {the_date}
AO: {ao_name}
Q: {q_name} {the_coqs_names}
PAX: {pax_names}
FNGs: {fngs_formatted}
COUNT: {count}
{moleskine_msg}
        """

        # Decrypt password
        fernet = Fernet(os.environ[constants.PASSWORD_ENCRYPT_KEY].encode())
        email_password_decrypted = fernet.decrypt(region_record.email_password.encode()).decode()

        try:
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

    res = client.chat_postMessage(
        channel=chan,
        text="slackblast",
        username=f"{q_name} (via Slackblast)",
        icon_url=q_url,
        blocks=[msg_block, edit_block],
    )
    # client.chat_postMessage(channel=chan, text=post_msg, username=f'{q_name} (via Slackblast)', icon_url=q_url)
    logger.info("\nMessage posted to Slack! \n{}".format(post_msg))


def handle_backblast_edit_post(ack, body, logger, client, context, backblast_data) -> str:
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
    moleskine = safe_get(backblast_data, actions.BACKBLAST_MOLESKIN)

    message_metadata = body["view"]["blocks"][-1]["elements"][0]["text"]
    message_channel, message_ts = message_metadata.split("|")

    pax_names_list = get_user_names(pax, logger, client, return_urls=False) or [""]
    pax_formatted = get_pax(pax)
    pax_full_list = [pax_formatted]
    fngs_formatted = fngs
    if non_slack_pax != "None":
        pax_full_list.append(non_slack_pax)
        pax_names_list.append(non_slack_pax)
    if fngs != "None":
        pax_full_list.append(fngs)
        pax_names_list.append(fngs)
        fngs_formatted = str(fngs.count(",") + 1) + " " + fngs
    pax_formatted = ", ".join(pax_full_list)

    if the_coq == None:
        the_coqs_formatted = ""
    else:
        the_coqs_formatted = get_pax(the_coq)
        the_coqs_full_list = [the_coqs_formatted]
        the_coqs_formatted = ", " + ", ".join(the_coqs_full_list)

    moleskine_formatted = parse_moleskin_users(moleskine, client)

    q_name, q_url = get_user_names([the_q], logger, client, return_urls=True)
    q_name = (q_name or [""])[0]
    q_url = q_url[0]

    post_msg = f"""
*Slackblast*:
*{title}*
*DATE*: {the_date}
*AO*: <#{the_ao}>
*Q*: <@{the_q}>{the_coqs_formatted}
*PAX*: {pax_formatted}
*FNGS*: {fngs_formatted}
*COUNT*: {count}
{moleskine_formatted}
    """

    msg_block = {
        "type": "section",
        "text": {"type": "mrkdwn", "text": post_msg},
        "block_id": "msg_text",
    }

    edit_block = {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Edit this backblast", "emoji": True},
                "value": json.dumps(backblast_data),
                "action_id": actions.BACKBLAST_EDIT_BUTTON,
            }
        ],
        "block_id": actions.BACKBLAST_EDIT_BUTTON,
    }

    res = client.chat_update(
        channel=message_channel,
        ts=message_ts,
        text="slackblast",
        username=f"{q_name} (via Slackblast)",
        icon_url=q_url,
        blocks=[msg_block, edit_block],
    )
    logger.info("\nBackblast updated in Slack! \n{}".format(post_msg))


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
    moleskine = safe_get(preblast_data, actions.PREBLAST_MOLESKIN)
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
    if moleskine:
        body_list.append(moleskine)

    msg = "\n".join(body_list)
    client.chat_postMessage(
        channel=chan, text=msg, username=f"{q_name} (via Slackblast)", icon_url=q_url
    )
    logger.info("\nMessage posted to Slack! \n{}".format(msg))


def handle_config_post(ack, body, logger, client, context, config_data) -> str:
    ack()

    region_record: Region = DbManager.get_record(Region, id=context["team_id"])
    fernet = Fernet(os.environ[constants.PASSWORD_ENCRYPT_KEY].encode())
    email_password_encrypted = fernet.encrypt(
        safe_get(config_data, actions.CONFIG_EMAIL_PASSWORD).encode()
    ).decode()

    DbManager.update_record(
        Region,
        region_record.id,
        {
            Region.email_enabled: 1
            if safe_get(config_data, actions.CONFIG_EMAIL_ENABLE) == "enable"
            else 0,
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
        },
    )
