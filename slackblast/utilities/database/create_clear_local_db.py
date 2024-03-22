from utilities.database import get_engine, orm
from utilities.database.orm import Base, PaxminerAO, PaxminerUser
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateSchema
import os
from slack_sdk import WebClient


def create_tables():

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
        engine: Engine = get_engine(schema=schema)
        if not engine.has_schema(engine, schema):
            engine.execute(CreateSchema(schema))
        Base.metadata.create_all(engine)
        engine.dispose()


def initialize_tables():

    slack_bot_token = os.environ["SLACK_BOT_TOKEN"]
    client = WebClient(token=slack_bot_token)
    channels = client.conversations_list().get("channels")
    users = client.users_list().get("members")

    ao_list = [
        PaxminerAO(
            channel_id=c["id"],
            ao=c["name"],
            channel_created=c["created"],
            archived=1 if c["is_archived"] else 0,
            backblast=0,
        )
        for c in channels
    ]

    user_list = [
        PaxminerUser(
            user_id=u["id"],
            user_name=u["profile"]["display_name"],
            real_name=u["profile"]["real_name"],
            phone=u["profile"].get("phone"),
            email=u["profile"].get("email"),
        )
        for u in users
    ]

    session = orm.get_session(schema="f3devregion")
    session.add_all(ao_list)
    session.add_all(user_list)
    session.commit()
    session.close()


if __name__ == "__main__":
    create_tables()
