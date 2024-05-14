import copy
from datetime import datetime
from logging import Logger
from typing import Optional

import pytz
from slack_sdk.web import WebClient
from sqlalchemy import Integer
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Mapped, mapped_column

from utilities import constants
from utilities.database import DbManager
from utilities.database.orm import (
    AchievementsAwarded,
    AchievementsList,
    BaseClass,
    GetDBClass,
    Region,
    intpk,
    str45,
    str100,
    tinyint1,
)
from utilities.helper_functions import (
    safe_get,
    update_local_region_records,
)
from utilities.slack import actions, forms
from utilities.slack import orm as slack_orm


class WeaselbotRegions(BaseClass, GetDBClass):
    __tablename__ = "regions_copy"
    id: Mapped[intpk]
    paxminer_schema: Mapped[str100]
    slack_token: Mapped[str100]
    send_achievements: Mapped[tinyint1]
    send_aoq_reports: Mapped[tinyint1]
    achievement_channel: Mapped[str100]
    default_siteq: Mapped[Optional[str45]]
    NO_POST_THRESHOLD: Mapped[int] = mapped_column(Integer, default=2)
    REMINDER_WEEKS: Mapped[int] = mapped_column(Integer, default=2)
    HOME_AO_CAPTURE: Mapped[int] = mapped_column(Integer, default=8)
    NO_Q_THRESHOLD_WEEKS: Mapped[int] = mapped_column(Integer, default=4)
    NO_Q_THRESHOLD_POSTS: Mapped[int] = mapped_column(Integer, default=4)

    def get_id():
        return WeaselbotRegions.id


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


def build_config_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    # paxminer_schema = region_record.paxminer_schema
    # update_view_id = safe_get(body, actions.LOADING_ID)
    config_form = copy.deepcopy(forms.WEASELBOT_CONFIG_FORM)
    callback_id = actions.WEASELBOT_CONFIG_CALLBACK_ID
    trigger_id = safe_get(body, "trigger_id")

    try:
        weaselbot_achievements = DbManager.find_records(
            cls=AchievementsList,
            filters=[True],
            schema=region_record.paxminer_schema,
        )
    except ProgrammingError:
        weaselbot_achievements = None

    if not weaselbot_achievements:
        config_form = copy.deepcopy(forms.NO_WEASELBOT_CONFIG_FORM)
        config_form.post_modal(
            client=client,
            trigger_id=trigger_id,
            callback_id=callback_id,
            new_or_add="add",
            title_text="Weaselbot Settings",
            submit_button_text="None",
        )
    else:
        initial_features = []
        if region_record.send_achievements:
            initial_features.append("achievements")
        if region_record.send_aoq_reports:
            initial_features.append("kotter_reports")

        config_form.set_initial_values(
            {
                actions.WEASELBOT_ENABLE_FEATURES: initial_features,
                actions.WEASELBOT_ACHIEVEMENT_CHANNEL: region_record.achievement_channel,
                actions.WEASELBOT_KOTTER_CHANNEL: region_record.default_siteq,
                actions.WEASELBOT_KOTTER_WEEKS: region_record.NO_POST_THRESHOLD,
                actions.WEASELBOT_KOTTER_REMOVE_WEEKS: region_record.REMINDER_WEEKS,
                actions.WEASELBOT_HOME_AO_WEEKS: region_record.HOME_AO_CAPTURE,
                actions.WEASELBOT_Q_WEEKS: region_record.NO_Q_THRESHOLD_WEEKS,
                actions.WEASELBOT_Q_POSTS: region_record.NO_Q_THRESHOLD_POSTS,
            }
        )

        config_form.post_modal(
            client=client,
            trigger_id=trigger_id,
            callback_id=callback_id,
            new_or_add="add",
            title_text="Weaselbot Settings",
        )


def handle_config_form(body: dict, client: WebClient, logger: Logger, context: dict, region_record: Region):
    config_data = forms.WEASELBOT_CONFIG_FORM.get_selected_values(body)
    fields = {
        Region.send_achievements: 1
        if "achievements" in safe_get(config_data, actions.WEASELBOT_ENABLE_FEATURES)
        else 0,
        Region.send_aoq_reports: 1
        if "kotter_reports" in safe_get(config_data, actions.WEASELBOT_ENABLE_FEATURES)
        else 0,
        Region.achievement_channel: safe_get(config_data, actions.WEASELBOT_ACHIEVEMENT_CHANNEL),
        Region.default_siteq: safe_get(config_data, actions.WEASELBOT_KOTTER_CHANNEL),
        Region.NO_POST_THRESHOLD: safe_get(config_data, actions.WEASELBOT_KOTTER_WEEKS),
        Region.REMINDER_WEEKS: safe_get(config_data, actions.WEASELBOT_KOTTER_REMOVE_WEEKS),
        Region.HOME_AO_CAPTURE: safe_get(config_data, actions.WEASELBOT_HOME_AO_WEEKS),
        Region.NO_Q_THRESHOLD_WEEKS: safe_get(config_data, actions.WEASELBOT_Q_WEEKS),
        Region.NO_Q_THRESHOLD_POSTS: safe_get(config_data, actions.WEASELBOT_Q_POSTS),
    }
    DbManager.update_record(
        cls=Region,
        id=context["team_id"],
        fields=fields,
    )
    update_local_region_records()
