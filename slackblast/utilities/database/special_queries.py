from dataclasses import dataclass

from sqlalchemy import and_, case, func, select

from utilities.database import get_session
from utilities.database.orm import AttendanceNew, Event, EventType, Org, UserNew


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
            AttendanceNew.event_id,
            func.group_concat(case((AttendanceNew.attendance_type_id.in_([2, 3]), UserNew.f3_name), else_=None)).label(
                "planned_qs"
            ),
            func.max(case((AttendanceNew.user_id == user_id, 1), else_=0)).label("user_attending"),
            func.max(
                case(
                    (and_(AttendanceNew.user_id == user_id, AttendanceNew.attendance_type_id.in_([2, 3])), 1),
                    else_=0,
                )
            ).label("user_q"),
        )
        .select_from(AttendanceNew)
        .join(UserNew, UserNew.id == AttendanceNew.user_id)
        .group_by(AttendanceNew.event_id)
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
