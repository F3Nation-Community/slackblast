import argparse
import os
import sys

from sqlalchemy import text

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

import logging

from slack_sdk import WebClient
from sqlalchemy.engine import Engine
from sqlalchemy_utils import create_database, database_exists

from utilities.database import get_engine, get_session, orm

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
logger.addHandler(handler)

parser = argparse.ArgumentParser()


def create_tables():
    logger.info("Creating schemas and tables...")

    schema_table_map = {
        "slackblast": [
            # orm.Region,
            orm.OrgType,
            orm.Org,
            orm.EventCategory,
            orm.EventType,
            orm.Location,
            orm.Event,
            orm.EventType_x_Org,
            orm.AttendanceType,
            orm.User,
            orm.Attendance,
            orm.SlackUser,
            orm.EventTag,
            orm.EventTag_x_Org,
        ],
        "f3devregion": [
            orm.AchievementsList,
            orm.AchievementsAwarded,
        ],
    }

    for schema, tables in schema_table_map.items():
        tables = [t.__table__ for t in tables]
        engine: Engine = get_engine(schema=schema)
        if not database_exists(engine.url):
            create_database(engine.url)
        with engine.connect() as conn:
            orm.BaseClass.metadata.create_all(bind=conn, tables=tables)
        engine.dispose()

    logger.info("Schemas and tables created!")


def initialize_tables():
    logger.info("Initializing tables with data from Slack...")

    slack_bot_token = os.environ["SLACK_BOT_TOKEN"]
    client = WebClient(token=slack_bot_token)
    users = client.users_list().get("members")

    user_list = [
        orm.User(
            id=i + 1,
            f3_name=u["profile"]["display_name"] or u["profile"]["real_name"],
            email=u["profile"].get("email") or u["id"],
            # home_region_id=1,
        )
        for i, u in enumerate(users)
    ]

    slack_user_list = [
        orm.SlackUser(
            id=i + 1,
            slack_id=u["id"],
            slack_team_id=u["team_id"],
            user_name=u["profile"]["display_name"] or u["profile"]["real_name"],
            email=u["profile"].get("email") or u["id"],
            user_id=i + 1,
            avatar_url=u["profile"]["image_192"],
        )
        for i, u in enumerate(users)
    ]

    achievement_list = [
        orm.AchievementsList(
            name="The Priest",
            description="Post for 25 QSource lessons",
            verb="posting for 25 QSource lessons",
            code="the_priest",
        ),
        orm.AchievementsList(
            name="The Monk",
            description="Post at 4 QSources in a month",
            verb="posting at 4 QSources in a month",
            code="the_monk",
        ),
        orm.AchievementsList(
            name="Leader of Men",
            description="Q at 4 beatdowns in a month",
            verb="Qing at 4 beatdowns in a month",
            code="leader_of_men",
        ),
    ]

    org_type_list = [
        orm.OrgType(id=1, name="AO"),
        orm.OrgType(id=2, name="Region"),
        orm.OrgType(id=3, name="Area"),
        orm.OrgType(id=4, name="Sector"),
    ]

    event_category_list = [
        orm.EventCategory(
            id=1, name="1st F - Core Workout", description="The core F3 activity - must meet all 5 core principles."
        ),
        orm.EventCategory(
            id=2, name="1st F - Pre Workout", description="Pre-workout activities (pre-rucks, pre-runs, etc)."
        ),
        orm.EventCategory(
            id=3,
            name="1st F - Off the books",
            description="Fitness activities that didn't meet all 5 core principles (unscheduled, open to all men, etc).",  # noqa: E501
        ),
        orm.EventCategory(id=4, name="2nd F - Fellowship", description="General category for 2nd F events."),
        orm.EventCategory(id=5, name="3rd F - Faith", description="General category for 3rd F events."),
    ]

    event_type_list = [
        orm.EventType(id=1, name="Bootcamp", category_id=1, acronym="BC"),
        orm.EventType(id=2, name="Run", category_id=1, acronym="RU"),
        orm.EventType(id=3, name="Ruck", category_id=1, acronym="RK"),
        orm.EventType(id=4, name="QSource", category_id=3, acronym="QS"),
    ]

    attendance_type_list = [
        orm.AttendanceType(id=1, type="PAX"),
        orm.AttendanceType(id=2, type="Q"),
        orm.AttendanceType(id=3, type="Co-Q"),
    ]

    event_tag_list = [
        orm.EventTag(id=1, name="Open", color="Green"),
        orm.EventTag(id=2, name="VQ", color="Blue"),
        orm.EventTag(id=3, name="Manniversary", color="Yellow"),
        orm.EventTag(id=4, name="Convergence", color="Orange"),
    ]

    session = get_session(schema="f3devregion")
    session.add_all(achievement_list)
    session.commit()
    session.close()

    session = get_session(schema="slackblast")
    session.add_all(org_type_list)
    session.add_all(event_category_list)
    session.add_all(event_type_list)
    session.add_all(attendance_type_list)
    session.add_all(event_tag_list)
    session.add_all(user_list)
    session.commit()
    session.add_all(slack_user_list)
    session.commit()
    session.close()

    logger.info("Tables initialized!")


def drop_database():
    logger.info("Resetting database...")
    session = get_session()
    session.execute(text("DROP SCHEMA IF EXISTS f3devregion;"))
    session.execute(text("DROP SCHEMA IF EXISTS paxminer;"))
    session.execute(text("DROP SCHEMA IF EXISTS slackblast;"))
    session.commit()
    session.close()


if __name__ == "__main__":
    parser.add_argument("--reset", action="store_true", help="Reset the database")
    args = parser.parse_args()
    if args.reset:
        drop_database()
    create_tables()
    initialize_tables()
