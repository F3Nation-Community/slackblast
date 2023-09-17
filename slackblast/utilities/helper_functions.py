import os, sys
import pickle

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from utilities import sendmail, constants
from utilities.database.orm import PaxminerAO, PaxminerUser, Region, Backblast, Attendance, User
from utilities.database import DbManager
from datetime import datetime
from utilities.slack import actions
from utilities.constants import LOCAL_DEVELOPMENT
from typing import List
from fuzzywuzzy import fuzz
from slack_bolt.adapter.aws_lambda.lambda_s3_oauth_flow import LambdaS3OAuthFlow
from slack_bolt.oauth.oauth_settings import OAuthSettings
import re
from cryptography.fernet import Fernet
from slack_sdk.web import WebClient
import json
from sqlalchemy.exc import IntegrityError
from pymysql.err import IntegrityError as PymysqlIntegrityError
import requests


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
            if result.get(k):
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
                user_name = user[0].user_name
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
            user_name_search = re.sub("\s\(([\s\S]*?\))", "", user_name_search).replace(" ", "_")
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


def run_fuzzy_match(workspace_name: str) -> List[str]:
    """Run the fuzz match on the workspace name and return a list of possible matches"""
    paxminer_region_records = DbManager.execute_sql_query(
        "select schema_name from paxminer.regions"
    )
    regions_list = [r["schema_name"] for r in paxminer_region_records]

    ratio_dict = {}
    for region in regions_list:
        ratio_dict[region] = fuzz.ratio(region, workspace_name)

    return [k for k, v in sorted(ratio_dict.items(), key=lambda item: item[1], reverse=True)][:20]


def check_for_duplicate(
    q: str,
    ao: str,
    date: datetime.date,
    region_record: Region,
    logger,
    og_ts: str = None,
) -> bool:
    """Check if there is already a backblast for this AO and Q on this date"""
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
        is_duplicate = (
            len(backblast_dups) > 0 or len(attendance_dups) > 0
        ) and og_ts != backblast_dups[0].timestamp
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
    if paxminer_schema:
        logger.debug(f"PAXMiner schema for {team_id} is {paxminer_schema}")
        return paxminer_schema

    else:
        paxminer_region_records = DbManager.execute_sql_query("select * from paxminer.regions")

        for region in paxminer_region_records:
            slack_client = WebClient(region["slack_token"])

            ao_index = 0
            try:
                ao_records = DbManager.execute_sql_query(
                    f"select * from {region['schema_name']}.aos"
                )
                ao_records = [ao for ao in ao_records if ao["channel_id"] is not None]

                keep_trying = True
                while keep_trying and ao_index < len(ao_records):
                    try:
                        slack_response = slack_client.conversations_info(
                            channel=ao_records[ao_index]["channel_id"]
                        )
                        keep_trying = False
                    except Exception as e:
                        ao_index += 1

            except Exception as e:
                logger.debug("No AOs table, skipping...")
                continue

            pm_team_id = slack_response["channel"]["shared_team_ids"][0]
            if team_id == pm_team_id:
                logger.debug(f'PAXMiner schema for {team_id} is {region["schema_name"]}')
                return region["schema_name"]

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
        user_records = DbManager.find_records(
            PaxminerUser, filters=[True], schema=region_record.paxminer_schema
        )

    slack_user_ids = re.findall(r"<@([A-Z0-9]+)>", text)
    slack_user_names = get_user_names(
        slack_user_ids, logger, client, return_urls=False, user_records=user_records
    )

    slack_user_ids = [f"<@{user_id}>" for user_id in slack_user_ids]
    slack_user_names = [f"@{user_name}".replace(" ", "_") for user_name in slack_user_names or []]

    for old_value, new_value in zip(slack_user_ids, slack_user_names):
        text = text.replace(old_value, new_value, 1)
    return text


def get_region_record(team_id: str, body, context, client, logger) -> Region:
    region_record: Region = DbManager.get_record(Region, id=team_id)
    team_domain = safe_get(body, "team", "domain")

    if not region_record:
        try:
            team_info = client.team_info()
            team_name = team_info["team"]["name"]
        except Exception as error:
            team_name = team_domain
        paxminer_schema = get_paxminer_schema(team_id, logger)
        region_record: Region = DbManager.create_record(
            Region(
                team_id=team_id,
                bot_token=context["bot_token"],
                workspace_name=team_name,
                paxminer_schema=paxminer_schema,
                email_enabled=0,
                email_option_show=0,
                editing_locked=0,
            )
        )

    return region_record
