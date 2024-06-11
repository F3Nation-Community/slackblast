import copy
import json
import os
from datetime import datetime
from logging import Logger
from typing import Any, Dict, List

import requests
from requests_oauthlib import OAuth2Session
from slack_sdk import WebClient

from utilities import constants
from utilities.database import DbManager
from utilities.database.orm import Region, User
from utilities.helper_functions import parse_rich_block, replace_user_channel_ids, safe_get
from utilities.slack import actions, forms
from utilities.slack import orm as slack_orm


def build_strava_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    user_id = safe_get(body, "user_id") or safe_get(body, "user", "id")
    team_id = safe_get(body, "team_id") or safe_get(body, "team", "id")
    channel_id = safe_get(body, "channel_id") or safe_get(body, "channel", "id")
    # lambda_function_host = (
    #     safe_get(context, "lambda_request", "headers", "Host") or os.environ[constants.LOCAL_HOST_DOMAIN]
    # )  # noqa
    lambda_function_host = safe_get(context, "lambda_request", "headers", "Host")

    backblast_ts = body["message"]["ts"]
    backblast_meta = safe_get(body, "message", "metadata", "event_payload") or json.loads(
        safe_get(body, "message", "blocks", -1, "elements", 0, "value") or "{}"
    )
    moleskine = body["message"]["blocks"][1]
    moleskine_text = replace_user_channel_ids(parse_rich_block(moleskine), region_record, client, logger)
    if "COT:" in moleskine_text:
        moleskine_text = moleskine_text.split("COT:")[0]
    elif "Announcements" in moleskine_text:
        moleskine_text = moleskine_text.split("Announcements")[0]

    allow_strava: bool = (
        (user_id == backblast_meta[actions.BACKBLAST_Q])
        or (user_id in (backblast_meta[actions.BACKBLAST_COQ] or []))
        or (user_id in (backblast_meta[actions.BACKBLAST_PAX] or []))
        or (user_id in (backblast_meta[actions.BACKBLAST_OP] or []))
    )

    if allow_strava:
        update_view_id = safe_get(body, actions.LOADING_ID)
        user_records: List[User] = DbManager.find_records(
            User, filters=[User.user_id == user_id, User.team_id == team_id]
        )

        if len(user_records) == 0:
            title_text = "Connect Strava"
            redirect_stage = "" if constants.LOCAL_DEVELOPMENT else "Prod/"
            oauth = OAuth2Session(
                client_id=os.environ[constants.STRAVA_CLIENT_ID],
                redirect_uri=f"https://{lambda_function_host}/{redirect_stage}exchange_token",
                scope=["read,activity:read,activity:write"],
                state=f"{team_id}-{user_id}",
            )
            authorization_url, state = oauth.authorization_url("https://www.strava.com/oauth/authorize")
            strava_blocks = [
                slack_orm.ImageBlock(
                    image_url="https://slackblast-images.s3.amazonaws.com/btn_strava_connectwith_orange.png",
                    alt_text="Connect with Strava",
                ),
                slack_orm.ActionsBlock(
                    elements=[
                        slack_orm.ButtonElement(
                            label="Connect",
                            action=actions.STRAVA_CONNECT_BUTTON,
                            url=authorization_url,
                        )
                    ]
                ),
                slack_orm.ContextBlock(
                    element=slack_orm.ContextElement(
                        initial_value="Opens in a new window",
                    ),
                    action="context",
                ),
            ]
        else:
            title_text = "Choose Activity"
            user_record = user_records[0]
            strava_recent_activities = get_strava_activities(user_record)

            logger.info(f"recent activities found: {strava_recent_activities}")
            if len(strava_recent_activities) == 0:
                strava_blocks = [
                    slack_orm.SectionBlock(
                        label="No recent activities found. Please log an activity on Strava first.",
                    ),
                ]

            button_elements = []
            for activity in strava_recent_activities:
                date = datetime.strptime(activity["start_date_local"], "%Y-%m-%dT%H:%M:%SZ")
                date_fmt = date.strftime("%m-%d %H:%M")
                button_elements.append(
                    slack_orm.ButtonElement(
                        label=f"{date_fmt} - {activity['name']}"[:75],
                        action="-".join([actions.STRAVA_ACTIVITY_BUTTON, str(activity["id"])]),
                        value=json.dumps(
                            {
                                actions.STRAVA_ACTIVITY_ID: activity["id"],
                                actions.STRAVA_CHANNEL_ID: channel_id,
                                actions.STRAVA_BACKBLAST_TS: backblast_ts,
                                actions.STRAVA_BACKBLAST_TITLE: backblast_meta["title"],
                                # actions.STRAVA_BACKBLAST_MOLESKINE: moleskine_text[:1500],
                            }
                        ),
                        # TODO: add confirmation modal
                    )
                )
                strava_blocks = [slack_orm.ActionsBlock(elements=button_elements)]

        strava_form = slack_orm.BlockView(blocks=strava_blocks)

        strava_form.update_modal(
            client=client,
            view_id=update_view_id,
            callback_id=actions.STRAVA_CALLBACK_ID,
            title_text=title_text,
            submit_button_text="None",
            parent_metadata={actions.STRAVA_BACKBLAST_MOLESKINE: moleskine_text[:2500]},
        )
    else:
        client.chat_postEphemeral(
            text="Connecting Strava to this Slackblast is only allowed for the tagged PAX."
            "Please contact one of them to make changes.",
            channel=channel_id,
            user=user_id,
        )


def build_strava_modify_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    strava_metadata = json.loads(safe_get(body, "actions", 0, "value") or "{}")
    private_metadata = json.loads(safe_get(body, "view", "private_metadata") or "{}")
    strava_activity_id = strava_metadata[actions.STRAVA_ACTIVITY_ID]
    channel_id = strava_metadata[actions.STRAVA_CHANNEL_ID]
    backblast_ts = strava_metadata[actions.STRAVA_BACKBLAST_TS]
    backblast_title = strava_metadata[actions.STRAVA_BACKBLAST_TITLE]
    backblast_moleskine = private_metadata[actions.STRAVA_BACKBLAST_MOLESKINE]

    view_id = safe_get(body, "container", "view_id")
    backblast_metadata = {
        "strava_activity_id": strava_activity_id,
        "channel_id": channel_id,
        "backblast_ts": backblast_ts,
    }

    activity_description = backblast_moleskine.replace("*", "")
    # remove all text after `COT:` or `COT :` if it exists
    if "COT:" in activity_description:
        activity_description = activity_description.split("COT:")[0]
    activity_description += "\n\nLearn more about F3 at https://f3nation.com"

    modify_form = copy.deepcopy(forms.STRAVA_ACTIVITY_MODIFY_FORM)
    modify_form.set_initial_values(
        {
            actions.STRAVA_ACTIVITY_TITLE: backblast_title,
            actions.STRAVA_ACTIVITY_DESCRIPTION: activity_description,
        }
    )

    modify_form.update_modal(
        client=client,
        view_id=view_id,
        title_text="Modify Strava Activity",
        callback_id=actions.STRAVA_MODIFY_CALLBACK_ID,
        parent_metadata=backblast_metadata,
        submit_button_text="Modify Strava activity",
        close_button_text="Close without modifying",
        notify_on_close=True,
    )


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

    user_records: List[User] = DbManager.find_records(User, filters=[User.user_id == user_id, User.team_id == team_id])
    if user_records:
        user_record = user_records[0]
        DbManager.update_record(
            cls=User,
            id=user_record.id,
            fields={
                User.strava_access_token: response_json["access_token"],
                User.strava_refresh_token: response_json["refresh_token"],
                User.strava_expires_at: datetime.fromtimestamp(response_json["expires_at"]),
                User.strava_athlete_id: response_json["athlete"]["id"],
            },
        )
    else:
        DbManager.create_record(
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
        },
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

    msg = f"<@{user_id}> has connected this backblast to a Strava activity (<https://www.strava.com/activities/{strava_activity_id}|view on Strava>)!"  # noqa
    if (safe_get(activity_data, "calories") is not None) & (safe_get(activity_data, "distance") is not None):
        msg += f" He traveled {round(activity_data['distance'] * 0.00062137, 1)} miles :runner: and burned "
        msg += f"{activity_data['calories']} calories :fire:."
    elif safe_get(activity_data, "calories"):
        msg += f" He burned {activity_data['calories']} calories :fire:."
    elif safe_get(activity_data, "distance"):
        msg += f" He traveled {round(activity_data['distance'] * 0.00062137, 1)} miles :runner:."

    blocks = [
        slack_orm.SectionBlock(
            label=msg,
        ).as_form_field(),
        slack_orm.ImageBlock(
            image_url="https://slackblast-images.s3.amazonaws.com/api_logo_pwrdBy_strava_stack_light.png",
            alt_text="Powered by Strava",
        ).as_form_field(),
    ]

    client.chat_postMessage(
        channel=channel_id,
        thread_ts=backblast_ts,
        text=msg,
        blocks=blocks,
    )
