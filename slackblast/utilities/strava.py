from datetime import datetime
import json
from logging import Logger
import os
from typing import Any, Dict, List
from slack_sdk import WebClient
from utilities.slack import forms
from utilities.database import DbManager
from utilities.database.orm import Region, User
from utilities import constants
from utilities.slack import actions
from utilities.helper_functions import safe_get
import requests


def strava_exchange_token(event, context) -> dict:
    """Exchanges a Strava auth code for an access token."""
    team_id, user_id = event.get("queryStringParameters", {}).get("state").split("-")
    code = event.get("queryStringParameters", {}).get("code")
    if not code:
        r = {
            "statusCode": 400,
            "body": {"error": "No code provided."},
            "headers": {},
        }
        return r

    response = requests.post(
        url="https://www.strava.com/oauth/token",
        data={
            "client_id": os.environ[constants.STRAVA_CLIENT_ID],
            "client_secret": os.environ[constants.STRAVA_CLIENT_SECRET],
            "code": code,
            "grant_type": "authorization_code",
        },
    )
    response.raise_for_status()

    response_json = response.json()
    DbManager.create_record(  # TODO: make this a function that updates the record if it already exists
        User(
            team_id=team_id,
            user_id=user_id,
            strava_access_token=response_json["access_token"],
            strava_refresh_token=response_json["refresh_token"],
            strava_expires_at=datetime.fromtimestamp(response_json["expires_at"]),
            strava_athlete_id=response_json["athlete"]["id"],
        )
    )

    r = {
        "statusCode": 200,
        "body": {"message": "Authorization successful! You can return to Slack."},
        "headers": {},
    }

    return r


def check_and_refresh_strava_token(user_record: User) -> str:
    """Check if a Strava token is expired and refresh it if necessary."""
    if not user_record.strava_access_token:
        return None

    if user_record.strava_expires_at < datetime.now():
        request_url = "https://www.strava.com/api/v3/oauth/token"
        res = requests.post(
            request_url,
            data={
                "client_id": os.environ["STRAVA_CLIENT_ID"],
                "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
                "refresh_token": user_record.strava_refresh_token,
                "grant_type": "refresh_token",
            },
        )
        res.raise_for_status()
        data = res.json()
        access_token = data["access_token"]
        DbManager.update_record(
            cls=User,
            id=user_record.id,
            fields={
                User.strava_access_token: data["access_token"],
                User.strava_refresh_token: data["refresh_token"],
                User.strava_expires_at: datetime.fromtimestamp(data["expires_at"]),
            },
        )
    else:
        access_token = user_record.strava_access_token

    return access_token


def get_strava_activities(user_record: User) -> List[Dict]:
    """Get a list of Strava activities for a user."""
    if not user_record.strava_access_token:
        return []

    access_token = check_and_refresh_strava_token(user_record)
    request_url = "https://www.strava.com/api/v3/athlete/activities"
    res = requests.get(request_url, headers={"Authorization": f"Bearer {access_token}"}, params={"per_page": 10})
    res.raise_for_status()
    data = res.json()
    return data


def update_strava_activity(
    strava_activity_id: str,
    user_id: str,
    team_id: str,
    backblast_title: str,
    backblast_moleskine: str,
) -> Dict[str, Any]:
    """Update a Strava activity.

    Args:
        strava_activity_id (str): Strava activity ID
        user_id (str): Slack user ID
        team_id (str): Slack team ID
        backblast_title (str): Backblast title (used for updating activity name)
        backblast_moleskine (str): Backblast Moleskine (used for updating activity description)

    Returns:
        dict: Updated Strava activity data
    """
    user_records: List[User] = DbManager.find_records(User, filters=[User.user_id == user_id, User.team_id == team_id])
    user_record = user_records[0]

    access_token = check_and_refresh_strava_token(user_record)
    request_url = f"https://www.strava.com/api/v3/activities/{strava_activity_id}"
    res = requests.put(
        request_url,
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "name": backblast_title,
            "description": backblast_moleskine,
        }
        # data={
        #     "name": backblast_title,
        #     "description": backblast_moleskine,
        # },
    )
    res.raise_for_status()
    data = res.json()
    return data


def get_strava_activity(
    strava_activity_id: str,
    user_id: str,
    team_id: str,
) -> Dict[str, Any]:
    """Get a Strava activity.

    Args:
        strava_activity_id (str): Strava activity ID

    Returns:
        dict: Strava activity data
    """
    user_records: List[User] = DbManager.find_records(User, filters=[User.user_id == user_id, User.team_id == team_id])
    user_record = user_records[0]

    access_token = check_and_refresh_strava_token(user_record)

    request_url = f"https://www.strava.com/api/v3/activities/{strava_activity_id}"
    res = requests.get(
        request_url,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    res.raise_for_status()
    data = res.json()
    return data


def handle_strava_modify(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    strava_data: dict = forms.STRAVA_ACTIVITY_MODIFY_FORM.get_selected_values(body)
    event_type = safe_get(body, "type")
    metadata = json.loads(body["view"]["private_metadata"])
    strava_activity_id = metadata["strava_activity_id"]
    channel_id = metadata["channel_id"]
    backblast_ts = metadata["backblast_ts"]
    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")

    if (event_type != "view_closed") and strava_data:
        activity_data = update_strava_activity(
            strava_activity_id=strava_activity_id,
            user_id=user_id,
            team_id=team_id,
            backblast_title=strava_data[actions.STRAVA_ACTIVITY_TITLE],
            backblast_moleskine=strava_data[actions.STRAVA_ACTIVITY_DESCRIPTION],
        )
    else:
        activity_data = get_strava_activity(strava_activity_id=strava_activity_id, user_id=user_id, team_id=team_id)

    msg = f"<@{user_id}> has connected this backblast to a <https://www.strava.com/activities/{strava_activity_id}|Strava activity>!"
    if (safe_get(activity_data, "calories") is not None) & (safe_get(activity_data, "distance") is not None):
        msg += f" He traveled {round(activity_data['distance'] * 0.00062137, 1)} miles :runner: and burned "
        f"{activity_data['calories']} calories :fire:."
    elif safe_get(activity_data, "calories"):
        msg += f" He burned {activity_data['calories']} calories :fire:."
    elif safe_get(activity_data, "distance"):
        msg += f" He traveled {round(activity_data['distance'] * 0.00062137, 1)} miles :runner:."

    client.chat_postMessage(
        channel=channel_id,
        thread_ts=backblast_ts,
        text=msg,
    )
