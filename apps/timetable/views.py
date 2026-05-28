import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from pdf2image import convert_from_bytes
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List
from django.conf import settings
from .models import ClassSession, Semester, SessionRoom
from apps.rooms.models import Room, Building
import re
from datetime import datetime
import time as time_module

MODELS_TO_TRY = [
    'gemini-3.1-flash-lite', 
    'gemini-2.5-flash',
    'gemini-3.5-flash'
]

NON_PERMSITE_VENUES = {
    'ECN BLK 1-2',
    'ECN BLK',
    'B EBONG LT',
    'OLD BLH 10',
    'OLD BLH',
    'NEDU BLK UP',
    'CBN',
    'RM 49-50',
    'RM 49',
    'RM 50',
    'NEW BOT LAB 2',
    'NEW BOT LAB',
    'COMM CENTER',
    'LAH',
    'EBONG LT',
    'FES LH FF',
    'FES LH GF',
    'ACB RM 9A',
    'ACB RM',
    'MTH LAB',
    'TED LAB',
    'NEW BLH 2',
    'NEW BLH',
    'TETFUND',
}

VENUE_ALIASES = {
    'ELF LT': 'ELF HALL',
    'ELF': 'ELF HALL',
    'ELF HALL': 'ELF HALL',
    'LF 3': 'FL 3',
    'LF 4': 'FL 4',
    'GD 3': 'GD 3',
    'GD 4': 'GD 4',
}



def generate_with_fallback(client, contents, config):
    for model in MODELS_TO_TRY:
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            status = getattr(e, 'status_code', None)
            if status in (503, 429):
                print(f"{model} unavailable ({status}), trying next...")
                time_module.sleep(5)
                continue
            raise  # Re-raise unexpected errors
    raise Exception("All models unavailable. Try again later.")


def normalize_venue(raw_venue: str) -> str:
    venue = raw_venue.strip().upper()
    venue = venue.replace('.', '')
    venue = re.sub(r'\s+', ' ', venue)
    return VENUE_ALIASES.get(venue, venue)


def is_non_permsite_venue(venue: str) -> bool:
    normalized = venue.strip().upper()
    for bad_venue in NON_PERMSITE_VENUES:
        if normalized == bad_venue or normalized.startswith(bad_venue):
            return True
    return False


def split_and_filter_venues(raw_venue_string: str) -> list[str]:
    kept = []
    for part in re.split(r'[;,]', raw_venue_string or ''):
        normalized = normalize_venue(part)
        if normalized and not is_non_permsite_venue(normalized):
            kept.append(normalized)
    return kept


def derive_building_code(venue: str) -> str:
    if venue.startswith('GD'):
        return 'GD'

    if venue.startswith('ELF'):
        return 'ELF'

    if venue.startswith('Y-BLD'):
        return 'PTDF'

    match = re.match(r'^(.*?)\s+\d+[A-Z]?$', venue, re.IGNORECASE)
    if match:
        return match.group(1).strip().upper()

    return venue.strip().upper()

class ClassSessionSchema(BaseModel):
    day: str
    start_time: str  # e.g., "08:00"
    end_time: str    # e.g., "10:00"
    course_code: str
    venue: str
    level: str       # e.g., "300 Level"
    group: str       # e.g., "Group 1", can be empty

class TimetableExtraction(BaseModel):
    sessions: List[ClassSessionSchema]



class UploadTimetableView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        semester_id = request.data.get('semester_id')
        
        if not file_obj:
            return Response({"error": "No file provided"}, status=400)
            
        if not semester_id:
            return Response({"error": "semester_id is required"}, status=400)
            
        try:
            semester = Semester.objects.get(id=semester_id)
        except Semester.DoesNotExist:
            return Response({"error": "Invalid semester_id"}, status=404)

                # Initialize the new Client
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        file_bytes = file_obj.read()
        images = convert_from_bytes(file_bytes)
        
        all_sessions = []
        
        prompt = """
        You are a specialized data extraction assistant. Extract timetable data from the provided image. 
        Pay close attention to merged cells. If a course spans multiple time blocks, create one single 
        session with the combined start and end times. Infer the year/level from the headings (e.g., '100 Level', '200 Level').
        If group is mentioned, include it; otherwise leave empty string. Day should be exactly one of: Monday, Tuesday, Wednesday, Thursday, Friday.
        Time should be in HH:MM format like '08:00'.
        """

        for image_pil in images:
            # Use the new client.models.generate_content format
            response = generate_with_fallback(
                client=client,
                contents=[prompt, image_pil],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=TimetableExtraction,
                ),
            )
            
            if response.text:
                page_data = json.loads(response.text)
                all_sessions.extend(page_data.get("sessions", []))
                
        # Save to database: create one ClassSession and link one or more Room(s) via SessionRoom
        saved_count = 0
        skipped = 0
        response_data = []

        for s in all_sessions:
            try:
                start_t = datetime.strptime(s['start_time'], '%H:%M').time()
                end_t = datetime.strptime(s['end_time'], '%H:%M').time()
            except Exception:
                skipped += 1
                continue

            venue_parts = split_and_filter_venues(s.get('venue', ''))
            if not venue_parts:
                skipped += 1
                continue

            session = ClassSession.objects.create(
                semester=semester,
                course_code=s['course_code'],
                day_of_week=s['day'],
                level=s.get('level', ''),
                group=s.get('group', ''),
                start_time=start_t,
                end_time=end_t,
                raw_venue_text=s.get('venue', ''),
            )

            linked = 0
            for part in venue_parts:
                building_code = derive_building_code(part)
                building_obj, _ = Building.objects.get_or_create(code=building_code, defaults={'name': building_code})

                room_obj, _ = Room.objects.get_or_create(name=part, defaults={'building': building_obj})

                # link via through model
                SessionRoom.objects.get_or_create(class_session=session, room=room_obj)
                linked += 1
                response_data.append({**s, 'linked_room': room_obj.name, 'building': building_obj.code})

            if linked == 0:
                # nothing to link; delete session placeholder
                session.delete()
                skipped += 1
            else:
                saved_count += 1

        return Response({
            "message": "Extracted and saved successfully",
            "extracted_count": len(all_sessions),
            "saved_count": saved_count,
            "skipped_count": skipped,
            "data": response_data,
        })



