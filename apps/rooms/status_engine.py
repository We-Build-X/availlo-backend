from apps.timetable.models import ClassSession, Semester, SessionRoom
from datetime import datetime, date, time


def _session_payload(session):
    if not session:
        return None
    return {
        "course_code": session.course_code,
        "start_time": session.start_time.strftime("%H:%M"),
        "end_time": session.end_time.strftime("%H:%M"),
        "level": session.level,
        "group": session.group,
    }


def _minutes_between(t1: time, t2: time) -> float:
    """t2 - t1 in minutes (both time objects)."""
    d1 = datetime(2000, 1, 1, t1.hour, t1.minute, t1.second)
    d2 = datetime(2000, 1, 1, t2.hour, t2.minute, t2.second)
    return (d2 - d1).total_seconds() / 60


def _build_status(room, sessions, current_time):
    ongoing_session = None
    for session in sessions:
        if session.start_time <= current_time < session.end_time:
            ongoing_session = session
            break

    reference_time = ongoing_session.end_time if ongoing_session else current_time

    next_session = None
    for session in sessions:
        if session.start_time > reference_time:
            next_session = session
            break

    base = {
        "room": room.name,
        "source": "timetable",
        "confidence_level": "high",
    }

    if ongoing_session:
        mins_remaining = _minutes_between(current_time, ongoing_session.end_time)
        is_ending_soon = 0 < mins_remaining <= 15

        base["is_free"] = False
        base["current_session"] = _session_payload(ongoing_session)
        base["next_session"] = _session_payload(next_session)
        base["status"] = "ENDING_SOON" if is_ending_soon else "OCCUPIED"
        base["free_until"] = None
        base["next_available_time"] = ongoing_session.end_time.strftime("%H:%M")
        return base

    base["is_free"] = True
    base["current_session"] = None
    base["next_session"] = _session_payload(next_session)
    base["status"] = "FREE"
    base["free_until"] = next_session.start_time.strftime("%H:%M") if next_session else None
    base["next_available_time"] = None
    return base


def get_rooms_status_bulk(rooms, current_datetime):
    """
    Compute the status of many rooms using a fixed number of queries instead
    of 3 queries per room.

    Returns a dict mapping room.id -> status payload. If there is no active
    semester, every room maps to an {"error": ...} payload.
    """
    rooms = list(rooms)

    active_semester = Semester.objects.filter(is_active=True).first()
    if not active_semester:
        error = {"error": "No active semester found."}
        return {room.id: error for room in rooms}

    day_name = current_datetime.strftime("%A")  # e.g "Monday"
    current_time = current_datetime.time()

    room_ids = [room.id for room in rooms]

    # Single query: today's sessions for these rooms, joined to their room id.
    session_rooms = (
        SessionRoom.objects.filter(
            room_id__in=room_ids,
            class_session__semester=active_semester,
            class_session__day_of_week=day_name,
        )
        .select_related("class_session")
        .order_by("class_session__start_time")
    )

    # Group sessions by room id (kept in start_time order by the query above).
    sessions_by_room = {}
    for sr in session_rooms:
        sessions_by_room.setdefault(sr.room_id, []).append(sr.class_session)
    return {
        room.id: _build_status(room, sessions_by_room.get(room.id, []), current_time)
        for room in rooms
    }


def get_room_status(room, current_datetime):
    """Status for a single room. Thin wrapper over the bulk implementation."""
    return get_rooms_status_bulk([room], current_datetime)[room.id]
