from dataclasses import dataclass
from typing import Any, List

from sqlalchemy import and_, case, func, select

from utilities.database import get_session
from utilities.database.orm import Attendance, Event, EventTag, EventType, Location, Org, SlackUser, User
from utilities.slack import orm


@dataclass
class CalendarHomeQuery:
    event: Event
    org: Org
    event_type: EventType
    planned_qs: str = None
    user_attending: int = None
    user_q: int = None


def home_schedule_query(
    user_id: int, filters: list, limit: int = 45, open_q_only: bool = False
) -> list[CalendarHomeQuery]:
    session = get_session()
    # Create an alias for Attendance to use in the subquery
    # AttendanceAlias = aliased(AttendanceNew)

    # Create the subquery
    subquery = (
        select(
            Attendance.event_id,
            func.group_concat(case((Attendance.attendance_type_id.in_([2, 3]), User.f3_name), else_=None)).label(
                "planned_qs"
            ),
            func.max(case((Attendance.user_id == user_id, 1), else_=0)).label("user_attending"),
            func.max(
                case(
                    (and_(Attendance.user_id == user_id, Attendance.attendance_type_id.in_([2, 3])), 1),
                    else_=0,
                )
            ).label("user_q"),
        )
        .select_from(Attendance)
        .join(User, User.id == Attendance.user_id)
        .group_by(Attendance.event_id)
        .alias()
    )

    if open_q_only:
        filters.append(subquery.c.planned_qs == None)  # noqa: E711

    # Create the main query
    query = (
        session.query(Event, Org, EventType, subquery.c.planned_qs, subquery.c.user_attending, subquery.c.user_q)
        .join(Org, Org.id == Event.org_id)
        .join(EventType, EventType.id == Event.event_type_id)
        .outerjoin(subquery, subquery.c.event_id == Event.id)
        .filter(*filters)
        .order_by(Event.start_date, Org.name, Event.start_time)
        .limit(limit)
    )

    # To execute the query and fetch all results
    results = query.all()
    output = [CalendarHomeQuery(*result) for result in results]
    session.close()
    return output


@dataclass
class EventExtended:
    event: Event
    org: Org
    event_type: EventType
    location: Location
    event_tag: EventTag


@dataclass
class AttendanceExtended:
    attendance: Attendance
    user: User
    slack_user: SlackUser


@dataclass
class PreblastInfo:
    event_extended: EventExtended
    attendance_records: list[AttendanceExtended]
    preblast_blocks: list[orm.BaseBlock]
    action_blocks: list[orm.BaseElement]
    user_is_q: bool = False


def event_preblast_query(event_id: int) -> tuple[EventExtended, list[AttendanceExtended]]:
    with get_session() as session:
        query = (
            session.query(Event, Org, EventType, Location, EventTag)
            .select_from(Event)
            .join(Org, Org.id == Event.org_id)
            .join(EventType, EventType.id == Event.event_type_id)
            .join(Location, Location.id == Event.location_id)
            .join(EventTag, EventTag.id == Event.event_tag_id, isouter=True)
            .filter(Event.id == event_id)
        )
        record = EventExtended(*query.one_or_none())

        query = (
            session.query(Attendance, User, SlackUser)
            .select_from(Attendance)
            .join(User)
            .join(SlackUser)
            .filter(Attendance.event_id == event_id, Attendance.is_planned)
        )
        attendance_records = [AttendanceExtended(*r) for r in query.all()]

    return record, attendance_records


def event_attendance_query(attendance_filter: List[Any] = None, event_filter: List[Any] = None) -> List[EventExtended]:
    with get_session() as session:
        attendance_subquery = (
            select(Attendance.event_id.distinct().label("event_id")).filter(*(attendance_filter or [])).alias()
        )
        event_records = (
            session.query(Event, Org, EventType, Location, EventTag)
            .select_from(Event)
            .join(Org, Org.id == Event.org_id)
            .join(EventType, EventType.id == Event.event_type_id)
            .join(Location, Location.id == Event.location_id)
            .join(EventTag, EventTag.id == Event.event_tag_id, isouter=True)
            .join(attendance_subquery, attendance_subquery.c.event_id == Event.id)
            .filter(*(event_filter or []))
        ).all()
        return [EventExtended(*r) for r in event_records]
