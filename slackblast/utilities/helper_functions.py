import os
import re
from logging import Logger
from typing import Any, Dict, List, Tuple

import boto3
import requests
from PIL import Image
from slack_bolt.adapter.aws_lambda.lambda_s3_oauth_flow import LambdaS3OAuthFlow
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.web import WebClient

from utilities import constants
from utilities.constants import LOCAL_DEVELOPMENT
from utilities.database import DbManager
from utilities.database.orm import (
    EventTag_x_Org,
    EventType_x_Org,
    Org,
    SlackSettings,
    SlackUser,
    User,
)
from utilities.slack import actions

REGION_RECORDS: Dict[str, SlackSettings] = {}
SLACK_USERS: Dict[str, SlackUser] = {}


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


def get_pax(pax):
    p = ""
    for x in pax:
        p += "<@" + x + "> "
    return p


def get_channel_names(
    array_of_channel_ids,
    logger: Logger,
    client: WebClient,
):
    names = []
    channel_records = client.conversations_list().get("channels")

    for channel_id in array_of_channel_ids:
        channel = [u for u in channel_records if u.get("id") == channel_id]
        if channel:
            channel_name = channel[0].get("name")
        else:
            channel_info_dict = client.conversations_info(channel=channel_id)
            channel_name = safe_get(channel_info_dict, "channel", "name") or None
        if channel_name:
            names.append(channel_name)

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
):
    names = []
    urls = []

    update_local_slack_users()

    for user_id in array_of_user_ids:
        user: SlackUser = safe_get(SLACK_USERS, user_id)
        names.append(user.user_name)
        urls.append(user.avatar_url)

    if return_urls:
        return names, urls
    else:
        return names


def get_user(slack_user_id: str, region_record: SlackSettings, client: WebClient, logger: Logger) -> SlackUser:
    if not SLACK_USERS:
        update_local_slack_users()

    user: SlackUser | None = safe_get(SLACK_USERS, slack_user_id)
    if not user:
        try:
            # check to see if this user's email is already in the db
            user_info = client.users_info(user=slack_user_id)
            email = safe_get(user_info, "user", "profile", "email")
            email = email or slack_user_id  # this means it's a bot
            user_name = safe_get(user_info, "user", "profile", "display_name") or safe_get(
                user_info, "user", "profile", "real_name"
            )
            avatar_url = safe_get(user_info, "user", "profile", "image_192")
            user_record = safe_get(DbManager.find_records(User, filters=[User.email == email]), 0)

            # If not, create a new user record
            if not user_record:
                user_record = DbManager.create_record(
                    User(
                        email=email,
                        f3_name=user_name,
                        home_region_id=region_record.org_id,
                    )
                )

            # Create a new slack user record
            slack_user_record = DbManager.create_record(
                SlackUser(
                    user_id=user_record.id,
                    slack_id=slack_user_id,
                    email=email,
                    user_name=user_name,
                    avatar_url=avatar_url,
                )
            )

            # Update SLACK_USERS with the new id
            SLACK_USERS[slack_user_id] = slack_user_record
            return slack_user_record
        except Exception as e:
            raise e
    else:
        return user


def update_local_slack_users() -> None:
    print("Updating local slack users...")
    slack_users: List[SlackUser] = DbManager.find_records(SlackUser, filters=[True])
    global SLACK_USERS
    SLACK_USERS = {slack_user.slack_id: slack_user for slack_user in slack_users}


def get_region_record(team_id: str, body, context, client, logger) -> SlackSettings:
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

        region_record = SlackSettings(
            team_id=team_id,
            bot_token=context["bot_token"],
            workspace_name=team_name,
            email_enabled=0,
            email_option_show=0,
            editing_locked=0,
        )

        org_record = Org(
            org_type_id=2,
            name=team_name,
            is_active=True,
            slack_id=team_id,
        )
        org_record: Org = DbManager.create_record(org_record)
        region_record.org_id = org_record.id
        DbManager.update_record(Org, org_record.id, {Org.slack_app_settings: region_record.to_json()})

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

        event_tag_x_org_records = [
            EventTag_x_Org(
                org_id=org_record.id,
                event_tag_id=i,
            )
            for i in range(1, 5)
        ]
        DbManager.create_records(event_tag_x_org_records)

        populate_users(client, team_id)

    return region_record


def populate_users(client: WebClient, team_id: str):
    users = client.users_list().get("members")
    user_list = [
        User(
            f3_name=u["profile"]["display_name"] or u["profile"]["real_name"],
            email=u["profile"].get("email") or u["id"],
        )
        for u in users
    ]
    DbManager.create_or_ignore(User, user_list)

    users_all: List[User] = DbManager.find_records(User, filters=[True])
    users_dict = {u.email: u.id for u in users_all}

    slack_user_list = [
        SlackUser(
            slack_id=u["id"],
            user_id=users_dict.get(u["profile"].get("email") or u["id"]),
            user_name=u["profile"]["display_name"] or u["profile"]["real_name"],
            email=u["profile"].get("email") or u["id"],
            avatar_url=u["profile"]["image_192"],
            slack_team_id=team_id,
        )
        for u in users
    ]
    DbManager.create_or_ignore(SlackUser, slack_user_list)
    update_local_slack_users()


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
    org_records: List[Org] = DbManager.find_records(Org, filters=[Org.org_type_id == 2])
    region_records = [SlackSettings(**org.slack_app_settings) for org in org_records]
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
    region_record: SlackSettings,
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
    channel_records = None
    USER_PATTERN = r"<@([A-Z0-9]+)>"
    CHANNEL_PATTERN = r"<#([A-Z0-9]+)(?:\|[A-Za-z\d]+)?>"

    text = text.replace("{}", "")

    slack_user_ids = re.findall(USER_PATTERN, text or "")
    slack_user_names = get_user_names(slack_user_ids, logger, client, return_urls=False)
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


def remove_keys_from_dict(d, keys_to_remove):
    if isinstance(d, dict):
        return {
            key: remove_keys_from_dict(value, keys_to_remove) for key, value in d.items() if key not in keys_to_remove
        }
    elif isinstance(d, list):
        return [remove_keys_from_dict(item, keys_to_remove) for item in d]
    else:
        return d


def safe_convert(value: str | None, conversion, args: list = None) -> Any | None:
    args = args or []
    try:
        return conversion(value, *args)
    except TypeError:
        return None


def time_int_to_str(time: int) -> str:
    return f"{time // 100:02d}:{time % 100:02d}"


def time_str_to_int(time: str) -> int:
    return int(time.replace(":", ""))


def upload_files_to_s3(
    files: List[Dict[str, str]], user_id: str, client: WebClient, logger: Logger
) -> Tuple[List[str], List[Dict[str, Any]]]:
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

    return file_list, file_send_list
