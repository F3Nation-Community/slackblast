from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, Date
from sqlalchemy.types import JSON
from sqlalchemy.dialects.mysql import LONGTEXT, TINYINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class BaseClass(DeclarativeBase):
    pass


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
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[str] = mapped_column(String(100))
    workspace_name: Mapped[Optional[str]]
    bot_token: Mapped[Optional[str]]
    paxminer_schema: Mapped[Optional[str]]
    email_enabled: Mapped[TINYINT] = mapped_column(TINYINT, default=0)
    email_server: Mapped[Optional[str]]
    email_server_port: Mapped[Optional[int]]
    email_user: Mapped[Optional[str]]
    email_password: Mapped[Optional[LONGTEXT]]
    email_to: Mapped[Optional[str]]
    email_option_show: Mapped[TINYINT] = mapped_column(TINYINT, default=0)
    postie_format: Mapped[Optional[TINYINT]] = mapped_column(TINYINT, default=1)
    editing_locked: Mapped[TINYINT] = mapped_column(TINYINT, default=0)
    default_destination: Mapped[Optional[str]] = mapped_column(String(30), default="ao_channel")
    backblast_moleskin_template: Mapped[Optional[JSON]]
    preblast_moleskin_template: Mapped[Optional[JSON]]
    strava_enabled: Mapped[TINYINT] = mapped_column(TINYINT, default=0)
    custom_fields: Mapped[Optional[JSON]]
    welcome_dm_enable = Mapped[Optional[TINYINT]]
    welcome_dm_template = Mapped[Optional[JSON]]
    welcome_channel_enable = Mapped[Optional[TINYINT]]
    welcome_channel = Mapped[Optional[str]]
    created: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # def get_id(self):
    #     return self.team_id

    def get_id():
        return Region.team_id


class Backblast(BaseClass, GetDBClass):
    __tablename__ = "beatdowns"
    timestamp = mapped_column("timestamp", String(45), primary_key=True)
    ts_edited = mapped_column("ts_edited", String(45))
    ao_id = mapped_column("ao_id", String(45))
    bd_date = mapped_column("bd_date", Date)
    q_user_id = mapped_column("q_user_id", String(45))
    coq_user_id = mapped_column("coq_user_id", String(45))
    pax_count = mapped_column("pax_count", Integer)
    backblast = mapped_column("backblast", LONGTEXT)
    fngs = mapped_column("fngs", String(45))
    fng_count = mapped_column("fng_count", Integer)
    json = mapped_column("json", JSON)

    # def get_id(self):
    #     return self.timestamp

    def get_id():
        return Backblast.timestamp


class Attendance(BaseClass, GetDBClass):
    __tablename__ = "bd_attendance"
    timestamp = mapped_column("timestamp", String(45), primary_key=True)
    ts_edited = mapped_column("ts_edited", String(45))
    user_id = mapped_column("user_id", String(45), primary_key=True)
    ao_id = mapped_column("ao_id", String(45))
    date = mapped_column("date", String(45))
    q_user_id = mapped_column("q_user_id", String(45))
    json = mapped_column("json", JSON)

    # def get_id(self):
    #     return self.timestamp

    def get_id():
        return Attendance.timestamp


class User(BaseClass, GetDBClass):
    __tablename__ = "slackblast_users"
    id = mapped_column("id", Integer, primary_key=True)
    team_id = mapped_column("team_id", String(100))
    user_id = mapped_column("user_id", String(100))
    strava_access_token = mapped_column("strava_access_token", String(100))
    strava_refresh_token = mapped_column("strava_refresh_token", String(100))
    strava_expires_at = mapped_column("strava_expires_at", DateTime)
    strava_athlete_id = mapped_column("strava_athlete_id", Integer)
    created = mapped_column("created", DateTime, default=datetime.utcnow)
    updated = mapped_column("updated", DateTime, default=datetime.utcnow)

    # def get_id(self):
    #     return self.id

    def get_id():
        return User.id


class PaxminerUser(BaseClass, GetDBClass):
    __tablename__ = "users"
    user_id = mapped_column("user_id", String(45), primary_key=True)
    user_name = mapped_column("user_name", String(45))
    real_name = mapped_column("real_name", String(45))
    phone = mapped_column("phone", String(45))
    email = mapped_column("email", String(45))
    start_date = mapped_column("start_date", String(45))
    app = mapped_column("app", Integer)

    # def get_id(self):
    #     return self.user_id

    def get_id():
        return PaxminerUser.user_id


class PaxminerAO(BaseClass, GetDBClass):
    __tablename__ = "aos"
    channel_id = mapped_column("channel_id", String(45), primary_key=True)
    ao = mapped_column("ao", String(45))
    channel_created = mapped_column("channel_created", Integer)
    archived = mapped_column("archived", Integer)
    backblast = mapped_column("backblast", Integer)

    # def get_id(self):
    #     return self.channel_id

    def get_id():
        return PaxminerAO.channel_id


class AchievementsList(BaseClass, GetDBClass):
    __tablename__ = "achievements_list"
    id = Column("id", Integer, primary_key=True)
    name = Column("name", String(255))
    description = Column("description", String(255))
    verb = Column("verb", String(255))
    code = Column("code", String(255))

    def get_id():
        return AchievementsList.id


class AchievementsAwarded(BaseClass, GetDBClass):
    __tablename__ = "achievements_awarded"
    id = Column("id", Integer, primary_key=True)
    achievement_id = Column("achievement_id", Integer)
    pax_id = Column("pax_id", String(255))
    date_awarded = Column("date_awarded", Date)
    created = Column("created", DateTime, default=datetime.utcnow)
    updated = Column("updated", DateTime, default=datetime.utcnow)

    def get_id():
        return AchievementsAwarded.id


# eventually this will be on the Regions table in Slackblast
class WeaselbotRegions(BaseClass, GetDBClass):
    __tablename__ = "regions_copy"
    id = Column("id", Integer, primary_key=True)
    paxminer_schema = Column("paxminer_schema", String(100))
    slack_token = Column("slack_token", String(100))
    send_achievements = Column("send_achievements", Integer)
    send_aoq_reports = Column("send_aoq_reports", Integer)
    achievement_channel = Column("achievement_channel", String(100))
    default_siteq_channel = Column("default_siteq", String(45))

    def get_id():
        return WeaselbotRegions.id


class PaxminerRegion(BaseClass, GetDBClass):
    __tablename__ = "regions_view"
    region = Column("region", String(45), primary_key=True)
    slack_token = Column("slack_token", String(90))
    schema_name = Column("schema_name", String(45))
    active = Column("active", Integer)
    firstf_channel = Column("firstf_channel", String(45))
    contact = Column("contact", String(45))
    send_pax_charts = Column("send_pax_charts", Integer)
    send_ao_leaderboard = Column("send_ao_leaderboard", Integer)
    send_q_charts = Column("send_q_charts", Integer)
    send_region_leaderboard = Column("send_region_leaderboard", Integer)
    send_region_uniquepax_chart = Column("send_region_uniquepax_chart", Integer)
    send_region_stats = Column("send_region_stats", Integer)
    send_mid_month_charts = Column("send_mid_month_charts", Integer)
    comments = Column("comments", LONGTEXT)

    def get_id():
        return PaxminerRegion.id
