from apps.timetable.models import ClassSession, Semester
from datetime import datetime

def get_room_status(room, current_datetime):
    # get active semester
    active_semester = Semester.objects.filter(is_active=True).first()
    if not active_semester:
        return {"error": "No active semester found."}

    day_name = current_datetime.strftime("%A")  # e.g "Monday"
    current_time = current_datetime.time()

    # find ongoing session
    ongoing_session = ClassSession.objects.filter(
        semester=active_semester,
        day_of_week=day_name,
        session_rooms__room=room,
        start_time__lte=current_time,
        end_time__gt=current_time  # strictly greater so room is free exactly at end time
    ).distinct().first()

    reference_time = ongoing_session.end_time if ongoing_session else current_time

    # find next session today
    next_session = ClassSession.objects.filter(
        semester=active_semester,
        day_of_week=day_name,
        session_rooms__room=room,
        start_time__gt=reference_time
    ).distinct().order_by('start_time').first()

    # build next session data if it exists
    next_session_data = None
    if next_session:
        next_session_data = {
            "course_code": next_session.course_code,
            "start_time": next_session.start_time.strftime("%H:%M"),
            "end_time": next_session.end_time.strftime("%H:%M"),
            "level": next_session.level,
            "group": next_session.group,
        }

    if ongoing_session:
        return {
            "room": room.name,
            "is_free": False,
            "source": "timetable",
            "confidence_level": "high",
            "current_session": {
                "course_code": ongoing_session.course_code,
                "start_time": ongoing_session.start_time.strftime("%H:%M"),
                "end_time": ongoing_session.end_time.strftime("%H:%M"),
                "level": ongoing_session.level,
                "group": ongoing_session.group,
            },
            "next_session": next_session_data
        }

    return {
        "room": room.name,
        "is_free": True,
        
        "source": "timetable",
        "confidence_level": "high",
        "current_session": None,
        "next_session": next_session_data  # tells student when it'll be occupied next
    }