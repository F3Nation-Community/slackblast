from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.dialects.mysql import BLOB, DATE, JSON, LONGTEXT, TEXT, TINYINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, registry
from typing_extensions import Annotated

mapper_registry = registry()

str30 = Annotated[str, String(30)]
str45 = Annotated[str, String(45)]
str90 = Annotated[str, String(90)]
str100 = Annotated[str, String(100)]
str255 = Annotated[str, String(255)]
intpk = Annotated[int, mapped_column(primary_key=True)]
tinyint = Annotated[int, TINYINT]
tinyint0 = Annotated[int, mapped_column(TINYINT, default=0)]
tinyint1 = Annotated[int, mapped_column(TINYINT, default=1)]
longtext = Annotated[str, LONGTEXT]
text = Annotated[str, TEXT]
json = Annotated[dict, JSON]
dt_create = Annotated[datetime, mapped_column(DateTime, default=datetime.utcnow)]
dt_update = Annotated[datetime, mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)]
str45pk = Annotated[str, mapped_column(String(45), primary_key=True)]
datepk = Annotated[date, mapped_column(DATE, primary_key=True)]
blob = Annotated[bytes, BLOB]


class BaseClass(DeclarativeBase):
    type_annotation_map = {
        str30: String(30),
        str45: String(45),
        str90: String(90),
        str100: String(100),
        str255: String(255),
        dict[str, Any]: JSON,
        longtext: LONGTEXT,
        text: TEXT,
    }


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
    id: Mapped[intpk]
    team_id: Mapped[str100]
    workspace_name: Mapped[Optional[str100]]
    bot_token: Mapped[Optional[str100]]
    paxminer_schema: Mapped[Optional[str100]]
    email_enabled: Mapped[tinyint0]
    email_server: Mapped[Optional[str100]]
    email_server_port: Mapped[Optional[int]]
    email_user: Mapped[Optional[str100]]
    email_password: Mapped[Optional[longtext]]
    email_to: Mapped[Optional[str100]]
    email_option_show: Mapped[Optional[tinyint0]]
    postie_format: Mapped[Optional[tinyint1]]
    editing_locked: Mapped[tinyint0]
    default_destination: Mapped[Optional[str]] = mapped_column(String(30), default="ao_channel")
    backblast_moleskin_template: Mapped[Optional[dict[str, Any]]]
    preblast_moleskin_template: Mapped[Optional[dict[str, Any]]]
    strava_enabled: Mapped[Optional[tinyint1]]
    custom_fields: Mapped[Optional[dict[str, Any]]]
    welcome_dm_enable: Mapped[Optional[tinyint]]
    welcome_dm_template: Mapped[Optional[dict[str, Any]]]
    welcome_channel_enable: Mapped[Optional[tinyint]]
    welcome_channel: Mapped[Optional[str100]]
    send_achievements: Mapped[Optional[tinyint1]]
    send_aoq_reports: Mapped[Optional[tinyint1]]
    achievement_channel: Mapped[Optional[str100]]
    default_siteq: Mapped[Optional[str45]]
    NO_POST_THRESHOLD: Mapped[Optional[int]] = mapped_column(Integer, default=2)
    REMINDER_WEEKS: Mapped[Optional[int]] = mapped_column(Integer, default=2)
    HOME_AO_CAPTURE: Mapped[Optional[int]] = mapped_column(Integer, default=8)
    NO_Q_THRESHOLD_WEEKS: Mapped[Optional[int]] = mapped_column(Integer, default=4)
    NO_Q_THRESHOLD_POSTS: Mapped[Optional[int]] = mapped_column(Integer, default=4)
    org_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orgs.id"))
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return Region.team_id


class Backblast(BaseClass, GetDBClass):
    __tablename__ = "beatdowns"
    timestamp: Mapped[Optional[str45]]
    ts_edited: Mapped[Optional[str45]]
    ao_id: Mapped[str45pk]
    bd_date: Mapped[datepk]
    q_user_id: Mapped[str45pk]
    coq_user_id: Mapped[Optional[str45]]
    pax_count: Mapped[Optional[int]]
    backblast: Mapped[Optional[longtext]]
    fngs: Mapped[Optional[str45]]
    fng_count: Mapped[Optional[int]]
    json: Mapped[Optional[dict[str, Any]]]

    def get_id():
        return Backblast.timestamp


class Attendance(BaseClass, GetDBClass):
    __tablename__ = "bd_attendance"
    timestamp: Mapped[Optional[str45]]
    ts_edited: Mapped[Optional[str45]]
    user_id: Mapped[str45pk]
    ao_id: Mapped[str45pk]
    date: Mapped[datepk]
    q_user_id: Mapped[str45pk]
    json: Mapped[Optional[dict[str, Any]]]

    def get_id():
        return Attendance.timestamp


class User(BaseClass, GetDBClass):
    __tablename__ = "slackblast_users"
    id: Mapped[intpk]
    team_id: Mapped[Optional[str100]]
    user_id: Mapped[Optional[str100]]
    strava_access_token: Mapped[Optional[str100]]
    strava_refresh_token: Mapped[Optional[str100]]
    strava_expires_at: Mapped[Optional[datetime]]
    strava_athlete_id: Mapped[Optional[int]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return User.id


class PaxminerUser(BaseClass, GetDBClass):
    __tablename__ = "users"
    user_id: Mapped[str45pk]
    user_name: Mapped[str45]
    real_name: Mapped[str45]
    phone: Mapped[Optional[str45]]
    email: Mapped[Optional[str45]]
    start_date: Mapped[Optional[date]]
    app: Mapped[tinyint0]
    json: Mapped[Optional[dict[str, Any]]]

    def get_id():
        return PaxminerUser.user_id


class PaxminerAO(BaseClass, GetDBClass):
    __tablename__ = "aos"
    channel_id: Mapped[str45pk]
    ao: Mapped[str45]
    channel_created: Mapped[int]
    archived: Mapped[tinyint]
    backblast: Mapped[tinyint]
    # site_q_user_id = Mapped[Optional[str]]

    def get_id():
        return PaxminerAO.channel_id


class AchievementsList(BaseClass, GetDBClass):
    __tablename__ = "achievements_list"
    id: Mapped[intpk]
    name: Mapped[str255]
    description: Mapped[longtext]
    verb: Mapped[str255]
    code: Mapped[str255]

    def get_id():
        return AchievementsList.id


class AchievementsAwarded(BaseClass, GetDBClass):
    __tablename__ = "achievements_awarded"
    id: Mapped[intpk]
    achievement_id: Mapped[int] = mapped_column(Integer, ForeignKey("achievements_list.id"))
    pax_id: Mapped[str255]
    date_awarded: Mapped[date]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return AchievementsAwarded.id


paxminer_region = Table(
    "regions",
    BaseClass.metadata,
    Column("region", String(45), primary_key=True),
    Column("slack_token", String(90)),
    Column("schema_name", String(45)),
    Column("active", TINYINT),
    Column("firstf_channel", String(45)),
    Column("contact", String(45)),
    Column("send_pax_charts", TINYINT),
    Column("send_ao_leaderboard", TINYINT),
    Column("send_q_charts", TINYINT),
    Column("send_region_leaderboard", TINYINT),
    Column("send_region_uniquepax_chart", TINYINT),
    Column("send_region_stats", String(45), default="0"),
    Column("send_mid_month_charts", String(45), default="0"),
    Column("comments", TEXT),
    schema="paxminer",
)


class PaxminerRegion(BaseClass, GetDBClass):
    __table__ = paxminer_region

    def get_id():
        return PaxminerRegion.schema_name


class Event(BaseClass, GetDBClass):
    __tablename__ = "events"

    id: Mapped[intpk]
    org_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orgs.id"))
    location_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("locations.id"))
    event_type_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("event_types.id"))
    series_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("events.id"))
    is_series: Mapped[bool]
    is_active: Mapped[bool]
    highlight: Mapped[bool]
    start_date: Mapped[date]
    end_date: Mapped[Optional[date]]
    start_time: Mapped[Optional[int]]
    end_time: Mapped[Optional[int]]
    day_of_week: Mapped[Optional[int]]
    name: Mapped[str100]
    description: Mapped[Optional[longtext]]
    recurrence_pattern: Mapped[Optional[str30]]
    recurrence_interval: Mapped[Optional[int]]
    index_within_interval: Mapped[Optional[int]]
    pax_count: Mapped[Optional[int]]
    fng_count: Mapped[Optional[int]]
    preblast: Mapped[Optional[longtext]]
    backblast: Mapped[Optional[longtext]]
    meta: Mapped[Optional[dict[str, Any]]]

    def get_id():
        return Event.id


class EventType(BaseClass, GetDBClass):
    __tablename__ = "event_types"

    id: Mapped[intpk]
    name: Mapped[str100]
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("event_categories.id"))
    description: Mapped[Optional[longtext]]

    def get_id():
        return EventType.id


class EventCategory(BaseClass, GetDBClass):
    __tablename__ = "event_categories"

    id: Mapped[intpk]
    name: Mapped[str100]
    description: Mapped[Optional[longtext]]

    def get_id():
        return EventCategory.id


class Location(BaseClass, GetDBClass):
    __tablename__ = "locations"

    id: Mapped[intpk]
    org_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orgs.id"))
    name: Mapped[str100]
    description: Mapped[Optional[longtext]]
    is_active: Mapped[bool]
    lat: Mapped[Optional[float]]
    lon: Mapped[Optional[float]]
    meta: Mapped[Optional[dict[str, Any]]]

    def get_id():
        return Location.id


class AttendanceNew(BaseClass, GetDBClass):
    __tablename__ = "attendance"

    id: Mapped[intpk]
    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"))
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("user.id"))
    attendance_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("attendance_types.id"))
    is_planned: Mapped[bool]
    meta: Mapped[Optional[dict[str, Any]]]

    def get_id():
        return AttendanceNew.id


class AttendanceType(BaseClass, GetDBClass):
    __tablename__ = "attendance_types"

    id: Mapped[intpk]
    type: Mapped[str100]
    description: Mapped[Optional[longtext]]

    def get_id():
        return AttendanceType.id


class Org(BaseClass, GetDBClass):
    __tablename__ = "orgs"

    id: Mapped[intpk]
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orgs.id"))
    org_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("org_types.id"))
    default_location_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("locations.id"))
    name: Mapped[str100]
    description: Mapped[Optional[longtext]]
    is_active: Mapped[bool]
    logo: Mapped[Optional[blob]]
    website: Mapped[Optional[str100]]
    email: Mapped[Optional[str100]]
    twitter: Mapped[Optional[str100]]
    facebook: Mapped[Optional[str100]]
    instagram: Mapped[Optional[str100]]
    slack_id: Mapped[Optional[str30]]
    slack_app_settings: Mapped[Optional[dict[str, Any]]]
    last_annual_review: Mapped[Optional[date]]
    meta: Mapped[Optional[dict[str, Any]]]

    def get_id():
        return Org.id


class OrgType(BaseClass, GetDBClass):
    __tablename__ = "org_types"

    id: Mapped[intpk]
    name: Mapped[str100]

    def get_id():
        return OrgType.id


class EventType_x_Org(BaseClass, GetDBClass):
    __tablename__ = "event_types_x_org"

    id: Mapped[intpk]
    event_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("event_types.id"))
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("orgs.id"))
    is_default: Mapped[bool]

    def get_id():
        return EventType_x_Org.id


class UserNew(BaseClass, GetDBClass):
    __tablename__ = "user"  # todo: change table name to users

    id: Mapped[intpk]
    f3_name: Mapped[str100]
    email: Mapped[str100]
    home_region_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orgs.id"))

    def get_id():
        return User.id


class SlackUser(BaseClass, GetDBClass):
    __tablename__ = "slack_users"

    id: Mapped[intpk]
    slack_id: Mapped[str100]
    user_name: Mapped[str100]
    email: Mapped[str100]
    user_id: Mapped[str100] = mapped_column(String(100), ForeignKey("user.user_id"))

    def get_id():
        return SlackUser.id
