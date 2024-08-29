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


def create_tables():
    logger.info("Creating schemas and tables...")

    schema_table_map = {
        "slackblast": [orm.Region, orm.User],
        "f3devregion": [
            orm.Backblast,
            orm.Attendance,
            orm.PaxminerUser,
            orm.PaxminerAO,
            orm.AchievementsList,
            orm.AchievementsAwarded,
        ],
        "paxminer": [orm.PaxminerRegion],
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
    channels = client.conversations_list().get("channels")
    users = client.users_list().get("members")

    ao_list = [
        orm.PaxminerAO(
            channel_id=c["id"],
            ao=c["name"],
            channel_created=c["created"],
            archived=1 if c["is_archived"] else 0,
            backblast=0,
        )
        for c in channels
    ]

    user_list = [
        orm.PaxminerUser(
            user_id=u["id"],
            user_name=u["profile"]["display_name"],
            real_name=u["profile"]["real_name"],
            phone=u["profile"].get("phone"),
            email=u["profile"].get("email"),
        )
        for u in users
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

    paxminer_region = [
        orm.PaxminerRegion(
            region="F3DevRegion",
            slack_token=os.environ["SLACK_BOT_TOKEN"],
            schema_name="f3devregion",
        )
    ]

    session = get_session(schema="f3devregion")
    session.add_all(ao_list)
    session.add_all(user_list)
    session.add_all(achievement_list)
    session.commit()
    session.close()

    session = get_session(schema="paxminer")
    session.add_all(paxminer_region)
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
    drop_database()
    create_tables()
    initialize_tables()
