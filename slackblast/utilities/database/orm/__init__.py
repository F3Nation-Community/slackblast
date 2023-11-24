from datetime import datetime
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Date
from sqlalchemy.types import JSON
from sqlalchemy.dialects.mysql import LONGTEXT

BaseClass = declarative_base(mapper=sqlalchemy.orm.mapper)


class GetDBClass:
    def get_id(self):
        return self.id

    def get(self, attr):
        if attr in [c.key for c in self.__table__.columns]:
            return getattr(self, attr)
        return None

    def to_json(self):
        return {c.key: self.get(c.key) for c in self.__table__.columns}

    def __repr__(self):
        return str(self.to_json())


class Region(BaseClass, GetDBClass):
    __tablename__ = "regions"
    id = Column("id", Integer, primary_key=True)
    team_id = Column("team_id", String(100))
    workspace_name = Column("workspace_name", String(100))
    bot_token = Column("bot_token", String(100))
    paxminer_schema = Column("paxminer_schema", String(45))
    email_enabled = Column("email_enabled", Integer)
    email_server = Column("email_server", String(100))
    email_server_port = Column("email_server_port", Integer)
    email_user = Column("email_user", String(100))
    email_password = Column("email_password", LONGTEXT)
    email_to = Column("email_to", String(100))
    email_option_show = Column("email_option_show", Integer)
    postie_format = Column("postie_format", Integer)
    editing_locked = Column("editing_locked", Integer)
    default_destination = Column("default_destination", String(30))
    backblast_moleskin_template = Column("backblast_moleskin_template", LONGTEXT)
    preblast_moleskin_template = Column("preblast_moleskin_template", LONGTEXT)
    strava_enabled = Column("strava_enabled", Integer)
    custom_fields = Column("custom_fields", JSON)
    created = Column("created", DateTime, default=datetime.utcnow)
    updated = Column("updated", DateTime, default=datetime.utcnow)

    # def get_id(self):
    #     return self.team_id

    def get_id():
        return Region.team_id


class Backblast(BaseClass, GetDBClass):
    __tablename__ = "beatdowns"
    timestamp = Column("timestamp", String(45), primary_key=True)
    ts_edited = Column("ts_edited", String(45))
    ao_id = Column("ao_id", String(45))
    bd_date = Column("bd_date", Date)
    q_user_id = Column("q_user_id", String(45))
    coq_user_id = Column("coq_user_id", String(45))
    pax_count = Column("pax_count", Integer)
    backblast = Column("backblast", LONGTEXT)
    fngs = Column("fngs", String(45))
    fng_count = Column("fng_count", Integer)
    json = Column("json", JSON)

    # def get_id(self):
    #     return self.timestamp

    def get_id():
        return Backblast.timestamp


class Attendance(BaseClass, GetDBClass):
    __tablename__ = "bd_attendance"
    timestamp = Column("timestamp", String(45), primary_key=True)
    ts_edited = Column("ts_edited", String(45))
    user_id = Column("user_id", String(45), primary_key=True)
    ao_id = Column("ao_id", String(45))
    date = Column("date", String(45))
    q_user_id = Column("q_user_id", String(45))
    json = Column("json", JSON)

    # def get_id(self):
    #     return self.timestamp

    def get_id():
        return Attendance.timestamp


class User(BaseClass, GetDBClass):
    __tablename__ = "slackblast_users"
    id = Column("id", Integer, primary_key=True)
    team_id = Column("team_id", String(100))
    user_id = Column("user_id", String(100))
    strava_access_token = Column("strava_access_token", String(100))
    strava_refresh_token = Column("strava_refresh_token", String(100))
    strava_expires_at = Column("strava_expires_at", DateTime)
    strava_athlete_id = Column("strava_athlete_id", Integer)
    created = Column("created", DateTime, default=datetime.utcnow)
    updated = Column("updated", DateTime, default=datetime.utcnow)

    # def get_id(self):
    #     return self.id

    def get_id():
        return User.id


class PaxminerUser(BaseClass, GetDBClass):
    __tablename__ = "users"
    user_id = Column("user_id", String(45), primary_key=True)
    user_name = Column("user_name", String(45))
    real_name = Column("real_name", String(45))
    phone = Column("phone", String(45))
    email = Column("email", String(45))
    start_date = Column("start_date", String(45))
    app = Column("app", Integer)

    # def get_id(self):
    #     return self.user_id

    def get_id():
        return PaxminerUser.user_id


class PaxminerAO(BaseClass, GetDBClass):
    __tablename__ = "aos"
    channel_id = Column("channel_id", String(45), primary_key=True)
    ao = Column("ao", String(45))
    channel_created = Column("channel_created", Integer)
    archived = Column("archived", Integer)
    backblast = Column("backblast", Integer)

    # def get_id(self):
    #     return self.channel_id

    def get_id():
        return PaxminerAO.channel_id
