from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BLOB, DATE, DECIMAL, JSON, LONGTEXT, TEXT, TINYINT
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
dt_create = Annotated[datetime, mapped_column(DateTime, default=datetime.now(timezone.utc))]
dt_update = Annotated[
    datetime, mapped_column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
]
str45pk = Annotated[str, mapped_column(String(45), primary_key=True)]
datepk = Annotated[date, mapped_column(DATE, primary_key=True)]
blob = Annotated[bytes, BLOB]
dec16_6 = Annotated[float, mapped_column(DECIMAL(16, 6))]


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
        return {c.key: self.get(c.key) for c in self.__table__.columns if c.key not in ["created", "updated"]}

    def __repr__(self):
        return str(self.to_json())

    def _update(self, fields):
        for k, v in fields.items():
            attr_name = str(k).split(".")[-1]
            setattr(self, attr_name, v)
            # if attr_name not in ["created", "updated"]:
            #     setattr(self, attr_name, v)
        return self


class SlackSettings(BaseClass, GetDBClass):
    __tablename__ = "regions"
    id: Mapped[intpk]
    team_id: Mapped[str100]
    workspace_name: Mapped[Optional[str100]]
    bot_token: Mapped[Optional[str100]]
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
    destination_channel: Mapped[Optional[str100]]
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
        return SlackSettings.team_id


# class User(BaseClass, GetDBClass):
#     __tablename__ = "slackblast_users"
#     id: Mapped[intpk]
#     team_id: Mapped[Optional[str100]]
#     user_id: Mapped[Optional[str100]]
#     strava_access_token: Mapped[Optional[str100]]
#     strava_refresh_token: Mapped[Optional[str100]]
#     strava_expires_at: Mapped[Optional[datetime]]
#     strava_athlete_id: Mapped[Optional[int]]
#     created: Mapped[dt_create]
#     updated: Mapped[dt_update]

#     def get_id():
#         return User.id


class AchievementsList(BaseClass, GetDBClass):
    __tablename__ = "achievements_list"
    id: Mapped[intpk]
    name: Mapped[str255]
    description: Mapped[longtext]
    verb: Mapped[str255]
    code: Mapped[str255]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

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


class Event(BaseClass, GetDBClass):
    __tablename__ = "events"

    id: Mapped[intpk]
    org_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orgs.id"))
    location_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("locations.id"))
    event_type_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("event_types.id"))
    event_tag_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("event_tags.id"))
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
    preblast_rich: Mapped[Optional[dict[str, Any]]]
    backblast_rich: Mapped[Optional[dict[str, Any]]]
    preblast_ts: Mapped[Optional[dec16_6]]
    backblast_ts: Mapped[Optional[dec16_6]]
    meta: Mapped[Optional[dict[str, Any]]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return Event.id


class EventType(BaseClass, GetDBClass):
    __tablename__ = "event_types"

    id: Mapped[intpk]
    name: Mapped[str100]
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("event_categories.id"))
    description: Mapped[Optional[longtext]]
    acronym: Mapped[Optional[str30]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return EventType.id


class EventCategory(BaseClass, GetDBClass):
    __tablename__ = "event_categories"

    id: Mapped[intpk]
    name: Mapped[str100]
    description: Mapped[Optional[longtext]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

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
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return Location.id


class User(BaseClass, GetDBClass):
    __tablename__ = "users"

    id: Mapped[intpk]
    f3_name: Mapped[str100]
    email: Mapped[str255] = mapped_column(String(255), unique=True)
    home_region_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orgs.id"))
    avatar_url: Mapped[Optional[str255]]
    meta: Mapped[Optional[dict[str, Any]]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return User.id


class SlackUser(BaseClass, GetDBClass):
    __tablename__ = "slack_users"

    id: Mapped[intpk]
    slack_id: Mapped[str100]
    user_name: Mapped[str100]
    email: Mapped[str255]
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    avatar_url: Mapped[Optional[str255]]
    slack_team_id: Mapped[str100]
    strava_access_token: Mapped[Optional[str100]]
    strava_refresh_token: Mapped[Optional[str100]]
    strava_expires_at: Mapped[Optional[datetime]]
    strava_athlete_id: Mapped[Optional[int]]
    meta: Mapped[Optional[dict[str, Any]]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return SlackUser.id


class Attendance(BaseClass, GetDBClass):
    __tablename__ = "attendance"

    id: Mapped[intpk]
    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("events.id"))
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    attendance_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("attendance_types.id"))
    is_planned: Mapped[bool]
    meta: Mapped[Optional[dict[str, Any]]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    __table_args__ = (UniqueConstraint("event_id", "user_id", "attendance_type_id", "is_planned", name="event_user"),)

    def get_id():
        return Attendance.id


class AttendanceType(BaseClass, GetDBClass):
    __tablename__ = "attendance_types"

    id: Mapped[intpk]
    type: Mapped[str100]
    description: Mapped[Optional[longtext]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

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
    email: Mapped[Optional[str255]]
    twitter: Mapped[Optional[str100]]
    facebook: Mapped[Optional[str100]]
    instagram: Mapped[Optional[str100]]
    slack_id: Mapped[Optional[str30]]
    slack_app_settings: Mapped[Optional[dict[str, Any]]]
    last_annual_review: Mapped[Optional[date]]
    meta: Mapped[Optional[dict[str, Any]]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return Org.id


class OrgType(BaseClass, GetDBClass):
    __tablename__ = "org_types"

    id: Mapped[intpk]
    name: Mapped[str100]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return OrgType.id


class EventType_x_Org(BaseClass, GetDBClass):
    __tablename__ = "event_types_x_org"

    id: Mapped[intpk]
    event_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("event_types.id"))
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("orgs.id"))
    is_default: Mapped[bool]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return EventType_x_Org.id


class EventTag(BaseClass, GetDBClass):
    __tablename__ = "event_tags"

    id: Mapped[intpk]
    name: Mapped[str100]
    description: Mapped[Optional[longtext]]
    color: Mapped[Optional[str30]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return EventTag.id


class EventTag_x_Org(BaseClass, GetDBClass):
    __tablename__ = "event_tags_x_org"

    id: Mapped[intpk]
    event_tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("event_tags.id"))
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("orgs.id"))
    color_override: Mapped[Optional[str30]]
    created: Mapped[dt_create]
    updated: Mapped[dt_update]

    def get_id():
        return EventTag_x_Org.id
