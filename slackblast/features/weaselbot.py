import copy
from datetime import datetime
from logging import Logger

import pytz
from slack_sdk.web import WebClient
from sqlalchemy.exc import ProgrammingError

from utilities import constants
from utilities.database import DbManager
from utilities.database.orm import (
    AchievementsAwarded,
    AchievementsList,
    Region,
    WeaselbotRegions,
)
from utilities.helper_functions import (
    safe_get,
)
from utilities.slack import actions, forms
from utilities.slack import orm as slack_orm


def build_achievement_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):

    paxminer_schema = region_record.paxminer_schema
    update_view_id = safe_get(body, actions.LOADING_ID)
    achievement_form = copy.deepcopy(forms.ACHIEVEMENT_FORM)
    callback_id = actions.ACHIEVEMENT_CALLBACK_ID

    # build achievement list
    achievement_list = []
    # gather achievements from paxminer
    if paxminer_schema:
        try:
            achievement_list = DbManager.find_records(schema=paxminer_schema, cls=AchievementsList, filters=[True])
        except ProgrammingError:
            error_form = copy.deepcopy(forms.ERROR_FORM)
            error_msg = constants.ERROR_FORM_MESSAGE_TEMPLATE.format(
                error="It looks like Weaselbot has not been set up for this region. Please contact your local Slack "
                "admin or go to https://github.com/F3Nation-Community/weaselbot to get started!"
            )
            error_form.set_initial_values({actions.ERROR_FORM_MESSAGE: error_msg})
            error_form.update_modal(
                client=client,
                view_id=update_view_id,
                title_text="Slackblast Error",
                submit_button_text="None",
                callback_id="error-id",
            )
            return
    if achievement_list:
        achievement_list = slack_orm.as_selector_options(
            names=[achievement.name for achievement in achievement_list],
            values=[str(achievement.id) for achievement in achievement_list],
            descriptions=[achievement.description for achievement in achievement_list],
        )
    else:
        achievement_list = slack_orm.as_selector_options(
            names=["No achievements available"],
            values=["None"],
        )

    achievement_form.set_initial_values(
        {
            actions.ACHIEVEMENT_DATE: datetime.now(pytz.timezone("US/Central")).strftime("%Y-%m-%d"),
        }
    )
    achievement_form.set_options(
        {
            actions.ACHIEVEMENT_SELECT: achievement_list,
        }
    )

    achievement_form.update_modal(
        client=client,
        view_id=update_view_id,
        callback_id=callback_id,
        title_text="Tag achievements",
    )

def handle_achievements_tag(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    achievement_data = forms.ACHIEVEMENT_FORM.get_selected_values(body)
    achievement_pax_list = safe_get(achievement_data, actions.ACHIEVEMENT_PAX)
    achievement_id = int(safe_get(achievement_data, actions.ACHIEVEMENT_SELECT))
    achievement_date = datetime.strptime(safe_get(achievement_data, actions.ACHIEVEMENT_DATE), "%Y-%m-%d")

    achievement_info = DbManager.get_record(AchievementsList, achievement_id, schema=region_record.paxminer_schema)
    achievement_name = achievement_info.name
    achievement_verb = achievement_info.verb

    paxminer_schema = region_record.paxminer_schema
    if paxminer_schema:
        weaselbot_region_info = safe_get(
            DbManager.find_records(
                cls=WeaselbotRegions,
                filters=[WeaselbotRegions.paxminer_schema == paxminer_schema],
                schema="weaselbot",
            ),
            0,
        )
        if weaselbot_region_info:
            achievement_channel = weaselbot_region_info.achievement_channel
        else:
            achievement_channel = None

    # Get all achievements for the year
    pax_awards = DbManager.find_records(
        schema=paxminer_schema,
        cls=AchievementsAwarded,
        filters=[
            AchievementsAwarded.pax_id.in_(achievement_pax_list),
            AchievementsAwarded.date_awarded >= datetime(achievement_date.year, 1, 1),
            AchievementsAwarded.date_awarded <= datetime(achievement_date.year, 12, 31),
        ],
    )
    pax_awards_total = {}
    pax_awards_this_achievement = {}
    for pax in achievement_pax_list:
        pax_awards_total[pax] = 0
        pax_awards_this_achievement[pax] = 0
    for award in pax_awards:
        pax_awards_total[award.pax_id] += 1
        if award.achievement_id == achievement_id:
            pax_awards_this_achievement[award.pax_id] += 1

    for pax in achievement_pax_list:
        msg = f"Congrats to our man <@{pax}>! He has achieved *{achievement_name}* for {achievement_verb}!"
        msg += f" This is achievement #{pax_awards_total[pax]+1} for him this year"
        if pax_awards_this_achievement[pax] > 0:
            msg += f" and #{pax_awards_this_achievement[pax]+1} time this year for this achievement."
        else:
            msg += "."
        client.chat_postMessage(channel=achievement_channel, text=msg)
        DbManager.create_record(
            schema=paxminer_schema,
            record=AchievementsAwarded(
                pax_id=pax,
                date_awarded=achievement_date,
                achievement_id=achievement_id,
            ),
        )
