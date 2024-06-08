import os
import pickle
import re
from datetime import datetime
from logging import Logger
from typing import Any, Dict, List, Tuple

from slack_bolt.adapter.aws_lambda.lambda_s3_oauth_flow import LambdaS3OAuthFlow
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.web import WebClient

from utilities import constants
from utilities.constants import LOCAL_DEVELOPMENT
from utilities.database import DbManager
from utilities.database.orm import (
    Attendance,
    Backblast,
    EventType_x_Org,
    Org,
    PaxminerAO,
    PaxminerRegion,
    PaxminerUser,
    Region,
    SlackUser,
    UserNew,
)
from utilities.slack import actions

REGION_RECORDS: Dict[str, Region] = {}
SLACK_USERS: Dict[str, str] = {}


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
    if not data:
        return None
    try:
        result = data
        for k in keys:
            if isinstance(k, int) and isinstance(result, list):
                result = result[k]
            elif result.get(k):
                result = result[k]
            else:
                return None
        return result
    except KeyError:
        return None


def get_channel_name(id, logger, client, region_record: Region = None):
    ao_record = None
    if region_record.paxminer_schema:
        ao_record = DbManager.get_record(PaxminerAO, id, region_record.paxminer_schema)

    if not ao_record:
        try:
            channel_info_dict = client.conversations_info(channel=id)
        except Exception as e:
            logger.error(e)
            return ""
        channel_name = safe_get(channel_info_dict, "channel", "name") or None
        logger.debug("channel_name is {}".format(channel_name))
        return channel_name
    else:
        return ao_record.ao


def get_channel_names(
    array_of_channel_ids,
    logger: Logger,
    client: WebClient,
    channel_records: List[PaxminerAO] = None,
):
    names = []

    if channel_records:
        for channel_id in array_of_channel_ids:
            channel = [u for u in channel_records if u.channel_id == channel_id]
            if channel:
                channel_name = channel[0].ao
            else:
                channel_info_dict = client.conversations_info(channel=channel_id)
                channel_name = safe_get(channel_info_dict, "channel", "name") or None
            if channel_name:
                names.append(channel_name)

    else:
        for channel_id in array_of_channel_ids:
            channel_info_dict = client.conversations_info(channel=channel_id)
            channel_name = safe_get(channel_info_dict, "channel", "name") or None
            if channel_name:
                names.append(channel_name)
            logger.debug("user_name is {}".format(channel_name))
        logger.debug("names are {}".format(names))

    return names


def get_channel_id(name, logger, client):
    channel_info_dict = client.conversations_list()
    channels = channel_info_dict["channels"]
    for channel in channels:
        if channel["name"] == name:
            return channel["id"]
    return None


def get_user_names(
    array_of_user_ids,
    logger,
    client: WebClient,
    return_urls=False,
    user_records: List[PaxminerUser] = None,
):
    names = []
    urls = []

    if user_records and not return_urls:
        for user_id in array_of_user_ids:
            user = [u for u in user_records if u.user_id == user_id]
            if user:
                user_name = user[0].user_name or user[0].real_name
            else:
                user_info_dict = client.users_info(user=user_id)
                user_name = (
                    safe_get(user_info_dict, "user", "profile", "display_name")
                    or safe_get(user_info_dict, "user", "profile", "real_name")
                    or None
                )
            if user_name:
                names.append(user_name)

    else:
        for user_id in array_of_user_ids:
            user_info_dict = client.users_info(user=user_id)
            user_name = (
                safe_get(user_info_dict, "user", "profile", "display_name")
                or safe_get(user_info_dict, "user", "profile", "real_name")
                or None
            )
            if user_name:
                names.append(user_name)
            logger.debug("user_name is {}".format(user_name))

            user_icon_url = user_info_dict["user"]["profile"]["image_192"]
            urls.append(user_icon_url)
        logger.debug("names are {}".format(names))

    if return_urls:
        return names, urls
    else:
        return names


def get_user_ids(user_names, client, user_records: List[PaxminerUser]):
    if user_records:
        member_list = {}
        for user in user_records:
            user_name_search = user.user_name.lower()
            user_name_search = re.sub(r"\s\(([\s\S]*?\))", "", user_name_search).replace(" ", "_")
            member_list[user_name_search] = user.user_id
    else:
        members = client.users_list()["members"]
        member_list = {}
        for member in members:
            member_dict = member["profile"]
            member_dict.update({"id": member["id"]})
            if member_dict["display_name"] == "":
                member_dict["display_name"] = member_dict["real_name"]
            member_dict["display_name"] = member_dict["display_name"].lower()
            member_dict["display_name"] = re.sub(r"\s\(([\s\S]*?\))", "", member_dict["display_name"]).replace(" ", "_")
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


def parse_moleskin_users(msg, client, user_records: List[PaxminerUser]):
    pattern = "@([A-Za-z0-9-_']+)"
    user_ids = get_user_ids(re.findall(pattern, msg), client, user_records)

    msg2 = re.sub(pattern, "{}", msg).format(*user_ids)
    return msg2


def get_pax(pax):
    p = ""
    for x in pax:
        p += "<@" + x + "> "
    return p


def check_for_duplicate(
    q: str,
    ao: str,
    date: datetime.date,
    region_record: Region,
    logger,
    og_ts: str = None,
) -> bool:
    """Check if there is already a backblast for this AO and Q on this date"""
    logger.debug(f"Checking for duplicate backblast for {q} at {ao} on {date}")
    if region_record.paxminer_schema:
        backblast_dups = DbManager.find_records(
            cls=Backblast,
            filters=[Backblast.q_user_id == q, Backblast.ao_id == ao, Backblast.bd_date == date],
            schema=region_record.paxminer_schema,
        )
        attendance_dups = DbManager.find_records(
            cls=Attendance,
            filters=[Attendance.q_user_id == q, Attendance.ao_id == ao, Attendance.date == date],
            schema=region_record.paxminer_schema,
        )
        logger.debug(f"Backblast dups: {backblast_dups}")
        logger.debug(f"og_ts: {og_ts}")
        is_duplicate = (len(backblast_dups) > 0 or len(attendance_dups) > 0) and og_ts != backblast_dups[0].timestamp
    else:
        is_duplicate = False

    return is_duplicate


def get_paxminer_schema(team_id: str, logger) -> str:
    """Scrapes the paxminer db to figure out this team's paxminer schema

    Args:
        team_id (str): slack internal team id

    Returns:
        str: returns the paxminer schema name
    """ """"""

    with open("data/paxminer_dict.pickle", "rb") as f:
        paxminer_dict = pickle.load(f)

    paxminer_schema = safe_get(paxminer_dict, team_id)
    slack_response = None
    if paxminer_schema:
        logger.debug(f"PAXMiner schema for {team_id} is {paxminer_schema}")
        return paxminer_schema

    else:
        paxminer_region_records = DbManager.find_records(PaxminerRegion, filters=[True], schema="paxminer")

        for region in paxminer_region_records:
            slack_client = WebClient(region.slack_token)

            ao_index = 0
            try:
                ao_records: List[PaxminerAO] = DbManager.find_records(
                    PaxminerAO, filters=[True], schema=region.schema_name
                )
                ao_records = [ao for ao in ao_records if ao.channel_id is not None]

                keep_trying = True
                while keep_trying and ao_index < len(ao_records):
                    try:
                        slack_response = slack_client.conversations_info(channel=ao_records[ao_index].channel_id)
                        keep_trying = False
                    except Exception:
                        ao_index += 1

            except Exception:
                logger.debug("No AOs table, skipping...")
                continue

            pm_team_id = safe_get(slack_response, "channel", "shared_team_ids", 0)
            if team_id == pm_team_id:
                logger.debug(f"PAXMiner schema for {team_id} is {region.schema_name}")
                return region.schema_name

        logger.debug(f"No PAXMiner schema found for {team_id}")
        return None


def replace_slack_user_ids(text: str, client, logger, region_record: Region = None) -> str:
    """Replace slack user ids with their user names

    Args:
        text (str): text with slack ids

    Returns:
        str: text with slack ids replaced
    """
    user_records = None
    if region_record.paxminer_schema:
        user_records = DbManager.find_records(PaxminerUser, filters=[True], schema=region_record.paxminer_schema)

    slack_user_ids = re.findall(r"<@([A-Z0-9]+)>", text or "")
    slack_user_names = get_user_names(slack_user_ids, logger, client, return_urls=False, user_records=user_records)

    slack_user_ids = [f"<@{user_id}>" for user_id in slack_user_ids]
    slack_user_names = [f"@{user_name}".replace(" ", "_") for user_name in slack_user_names or []]

    for old_value, new_value in zip(slack_user_ids, slack_user_names):
        text = text.replace(old_value, new_value, 1)
    return text


def get_user_id(slack_user_id: str, region_record: Region, client: WebClient, logger: Logger) -> int:
    if not SLACK_USERS:
        update_local_slack_users()

    user_id = safe_get(SLACK_USERS, slack_user_id)
    if not user_id:
        try:
            # check to see if this user's email is already in the db
            user_info = client.users_info(user=slack_user_id)
            email = safe_get(user_info, "user", "profile", "email")
            user_name = safe_get(user_info, "user", "profile", "display_name") or safe_get(
                user_info, "user", "profile", "real_name"
            )
            user_record = safe_get(DbManager.find_records(UserNew, filters=[UserNew.email == email]), 0)

            # If not, create a new user record
            if not user_record:
                user_record = DbManager.create_record(
                    UserNew(
                        email=email,
                        f3_name=user_name,
                        home_region_id=region_record.org_id,
                    )
                )

            # Create a new slack user record
            DbManager.create_record(
                SlackUser(
                    user_id=user_record.id,
                    slack_id=slack_user_id,
                    email=email,
                    user_name=user_name,
                )
            )

            # Update SLACK_USERS with the new id
            SLACK_USERS[slack_user_id] = user_record.id
            return user_record.id
        except Exception as e:
            raise e
    else:
        return user_id


def update_local_slack_users() -> None:
    print("Updating local slack users...")
    slack_users: List[SlackUser] = DbManager.find_records(SlackUser, filters=[True])
    global SLACK_USERS
    SLACK_USERS = {slack_user.slack_id: slack_user.user_id for slack_user in slack_users}


def get_region_record(team_id: str, body, context, client, logger) -> Region:
    if not REGION_RECORDS:
        update_local_region_records()

    region_record = safe_get(REGION_RECORDS, team_id)
    team_domain = safe_get(body, "team", "domain")

    if not region_record:
        try:
            team_info = client.team_info()
            team_name = team_info["team"]["name"]
        except Exception:
            team_name = team_domain

        paxminer_schema = get_paxminer_schema(team_id, logger)

        org_record = Org(
            org_type_id=2,
            name=team_name,
            is_active=True,
            slack_id=team_id,
        )
        org_record: Org = DbManager.create_record(org_record)

        region_record: Region = DbManager.create_record(
            Region(
                team_id=team_id,
                bot_token=context["bot_token"],
                workspace_name=team_name,
                paxminer_schema=paxminer_schema,
                email_enabled=0,
                email_option_show=0,
                editing_locked=0,
                org_id=org_record.id,
            )
        )
        REGION_RECORDS[team_id] = region_record

        event_type_x_org_records = [
            EventType_x_Org(
                org_id=org_record.id,
                event_type_id=i,
                is_default=False,
            )
            for i in range(1, 5)
        ]
        DbManager.create_records(event_type_x_org_records)

    return region_record


def get_request_type(body: dict) -> Tuple[str]:
    request_type = safe_get(body, "type")
    if request_type == "event_callback":
        return ("event_callback", safe_get(body, "event", "type"))
    elif request_type == "block_actions":
        block_action = safe_get(body, "actions", 0, "action_id")
        for action in actions.ACTION_PREFIXES:
            if block_action[: len(action)] == action:
                return ("block_actions", action)
        return ("block_actions", block_action)
    elif request_type == "view_submission":
        return ("view_submission", safe_get(body, "view", "callback_id"))
    elif not request_type and "command" in body:
        return ("command", safe_get(body, "command"))
    elif request_type == "view_closed":
        return ("view_closed", safe_get(body, "view", "callback_id"))
    else:
        return ("unknown", "unknown")


def update_local_region_records() -> None:
    print("Updating local region records...")
    region_records: List[Region] = DbManager.find_records(Region, filters=[True])
    global REGION_RECORDS
    REGION_RECORDS = {region.team_id: region for region in region_records}


def parse_rich_block(
    # client: WebClient,
    # logger: Logger,
    block: Dict[str, Any],
    # parse_users: bool = True,
    # parse_channels: bool = True,
    # region_record: Region = None,
) -> str:
    """Extracts the plain text representation from a rich text block.

    Args:
        client (WebClient): Slack client
        logger (Logger): Logger
        block (Dict[str, Any]): Block to parse
        parse_users (bool, optional): If True, user mentions will be parsed to their name. Defaults to True.
        parse_channels (bool, optional): If True, channel mentions will be parsed to its name. Defaults to True.

    Returns:
        str: Extracted plain text
    """

    def process_text_element(text, element):
        msg = ""
        if element["type"] == "rich_text_quote":
            msg += '"'
        if text["type"] == "text":
            msg += text["text"]
        if text["type"] == "emoji":
            msg += f':{text["name"]}:'
        if text["type"] == "link":
            msg += text["url"]
        if text["type"] == "user":
            msg += f'<@{text["user_id"]}>'
        if text["type"] == "channel":
            msg += f'<#{text["channel_id"]}>'
        if element["type"] == "rich_text_quote":
            msg += '"'
        return msg

    # user_list = []
    # channel_list = []
    # user_index = 0
    # channel_index = 0

    msg = ""

    for element in block["elements"]:
        if element["type"] in ["rich_text_section", "rich_text_preformatted", "rich_text_quote"]:
            for text in element["elements"]:
                msg += process_text_element(text, element)
        elif element["type"] == "rich_text_list":
            for list_num, item in enumerate(element["elements"]):
                line_msg = ""
                for text in item["elements"]:
                    line_msg += process_text_element(text, item)
                line_start = f"{list_num+1}. " if element["style"] == "ordered" else "- "  # TODO: handle nested lists
                msg += f"{line_start}{line_msg}\n"
    return msg


def replace_user_channel_ids(
    text: str,
    region_record: Region,
    client: WebClient,
    logger: Logger,
) -> str:
    """Replace user and channel ids with their names

    Args:
        text (str): text with slack ids
        region_record (Region): region record
        client (WebClient): slack client
        logger (Logger): logger

    Returns:
        str: text with slack ids replaced
    """
    user_records = None
    channel_records = None
    USER_PATTERN = r"<@([A-Z0-9]+)>"
    CHANNEL_PATTERN = r"<#([A-Z0-9]+)(?:\|[A-Za-z\d]+)?>"
    if region_record.paxminer_schema:
        user_records = DbManager.find_records(PaxminerUser, filters=[True], schema=region_record.paxminer_schema)
        channel_records = DbManager.find_records(PaxminerAO, filters=[True], schema=region_record.paxminer_schema)
    text = text.replace("{}", "")

    slack_user_ids = re.findall(USER_PATTERN, text or "")
    slack_user_names = get_user_names(slack_user_ids, logger, client, return_urls=False, user_records=user_records)
    text = re.sub(USER_PATTERN, "{}", text)
    text = text.format(*slack_user_names)

    slack_channel_ids = re.findall(CHANNEL_PATTERN, text or "")
    slack_channel_names = get_channel_names(slack_channel_ids, logger, client, channel_records=channel_records)

    text = re.sub(CHANNEL_PATTERN, "{}", text)
    text = text.format(*slack_channel_names)

    return text


def plain_text_to_rich_block(text: str) -> Dict[str, Any]:
    """Converts plain text to a rich text block

    Args:
        text (str): plain text

    Returns:
        Dict[str, Any]: rich text block
    """

    # split out bolded text using *
    split_text = re.split(r"(\*.*?\*)", text)
    text_elements = [
        (
            {"type": "text", "text": s.replace("*", ""), "style": {"bold": True}}
            if s.startswith("*")
            else {"type": "text", "text": s}
        )
        for s in split_text
    ]

    # now convert emojis
    final_text_elements = []
    for element in text_elements:
        if element["type"] == "text" and not element.get("style"):
            split_emoji_text = re.split(r"(:\S*?:)", element["text"])
            emoji_elements = [
                (
                    {"type": "emoji", "name": s.replace(":", "")}
                    if s.startswith(":") and s.endswith(":")
                    else {"type": "text", "text": s}
                )
                for s in split_emoji_text
            ]
            final_text_elements.extend(emoji_elements)
        else:
            final_text_elements.append(element)

    final_text_elements = [e for e in final_text_elements if e.get("text") != ""]

    return {
        "type": "rich_text",
        "elements": [
            {
                "type": "rich_text_section",
                "elements": final_text_elements,
            }
        ],
    }


def safe_convert(value: str | None, conversion, args=None) -> Any | None:
    args = args or []
    try:
        return conversion(value, *args)
    except TypeError:
        return None


def time_int_to_str(time: int) -> str:
    return f"{time // 100:02d}:{time % 100:02d}"


def time_str_to_int(time: str) -> int:
    return int(time.replace(":", ""))
