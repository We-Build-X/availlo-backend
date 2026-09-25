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
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, inline_serializer
from .serializers import ClassSessionAdminSerializer


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
    # split on semicolon, comma or slash to handle values like "ELF/TETFUND"
    parts = [p for p in re.split(r"[;,/]", raw_venue_string or '')]
    normalized_parts = [normalize_venue(p) for p in parts if p and p.strip()]

    # Special rule: when ELF and TETFUND appear together (e.g. "ELF LT./TETFUND",
    # "ELF/TETFUND"), prefer and return only TETFUND as the effective venue.
    has_elf = any(p.startswith('ELF') for p in normalized_parts)
    has_tetfund = any('TETFUND' in p for p in normalized_parts)
    if has_elf and has_tetfund:
        return ['TETFUND']

    kept = []
    for normalized in normalized_parts:
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


class AdminSessionPagination(PageNumberPagination):
    page_size = 10


def link_session_to_venue_parts(session: ClassSession, venue_parts: list[str]) -> list[Room]:
    """Create Building/Room rows as needed and sync SessionRoom links.

    Links in `venue_parts` are kept; stale links are removed.
    Returns the linked Room objects.
    """
    desired_rooms: list[Room] = []
    for part in venue_parts:
        building_code = derive_building_code(part)
        building_obj, _ = Building.objects.get_or_create(
            code=building_code, defaults={'name': building_code}
        )
        room_obj, _ = Room.objects.get_or_create(
            name=part, defaults={'building': building_obj}
        )
        if room_obj.building_id is None:
            room_obj.building = building_obj
            room_obj.save(update_fields=['building'])
        SessionRoom.objects.get_or_create(class_session=session, room=room_obj)
        desired_rooms.append(room_obj)
    if desired_rooms:
        SessionRoom.objects.filter(class_session=session).exclude(
            room__in=[r.id for r in desired_rooms]
        ).delete()
    return desired_rooms


def sync_session_rooms_from_raw(session: ClassSession, raw_venue_text: str) -> list[Room]:
    """Re-derive venue parts from raw text and sync SessionRoom links.

    Raises ValueError if no valid permsite venue remains.
    """
    venue_parts = split_and_filter_venues(raw_venue_text or '')
    if not venue_parts:
        raise ValueError("No valid permsite venue remains after normalization/filtering.")
    return link_session_to_venue_parts(session, venue_parts)

class ClassSessionSchema(BaseModel):
    day: str
    start_time: str  # e.g., "08:00"
    end_time: str    # e.g., "10:00"
    course_code: str
    venue: str
    level: str       # e.g., "300 Level"
    group: str       # e.g., "Group 1", can be empty

def normalize_semester_name(raw: str) -> str:
    name = (raw or "").strip()
    name = re.sub(r'\s+', ' ', name)
    return name


class TimetableExtraction(BaseModel):
    semester_name: str
    sessions: List[ClassSessionSchema]



class UploadTimetableView(APIView):
    parser_classes = [MultiPartParser]

    @extend_schema(
            summary="Upload timetable PDF",
            description="Upload a PDF file containing the timetable. The semester name is extracted verbatim from the timetable header and a Semester is auto-created (case-insensitive dedup). Re-uploading the same semester replaces existing sessions.",
            request=inline_serializer(
                name="TimetableUploadRequest",
                fields={
                    'file': serializers.FileField(),
                }

            ),
            responses={
                200: inline_serializer(
                    name="TimetableUploadResponse",
                    fields={
                        'message': serializers.CharField(),
                        'extracted_count': serializers.IntegerField(),
                        'saved_count': serializers.IntegerField(),
                        'skipped_count': serializers.IntegerField(),
                        'semester': serializers.DictField(),
                        'data': serializers.ListField(child=serializers.DictField()),
                    }
                ),
                400: inline_serializer(
                    name="TimetableUploadErrorResponse",
                    fields={
                        'error': serializers.CharField(),
                    }
                ),
            }
    )

    def post(self, request):

        file_obj = request.FILES.get('file')

        if not file_obj:
            return Response({"error": "No file provided"}, status=400)

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        file_bytes = file_obj.read()
        images = convert_from_bytes(file_bytes)

        all_sessions = []
        extracted_semester_name = None

        prompt = """
        You are a specialized data extraction assistant. Extract timetable data from the provided image.
        Pay close attention to merged cells. If a course spans multiple time blocks, create one single
        session with the combined start and end times. Infer the year/level from the headings (e.g., '100 Level', '200 Level').
        If group is mentioned, include it; otherwise leave empty string. Day should be exactly one of: Monday, Tuesday, Wednesday, Thursday, Friday.
        Time should be in HH:MM format like '08:00'.
        Also extract the semester/academic session title verbatim from the timetable header/title (e.g., "2024/2025 Second Semester", "2025/2026 First Semester Timetable"). Return it verbatim as semester_name, collapsed whitespace only, no reformatting. If not visible, return empty string.
        """

        for image_pil in images:
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
                if not extracted_semester_name:
                    candidate = normalize_semester_name(page_data.get("semester_name", ""))
                    if candidate:
                        extracted_semester_name = candidate
                all_sessions.extend(page_data.get("sessions", []))

        if not extracted_semester_name:
            return Response({"error": "Could not extract semester name from timetable header"}, status=400)

        semester = Semester.objects.filter(name__iexact=extracted_semester_name).first()
        if semester:
            created = False
            ClassSession.objects.filter(semester=semester).delete()
        else:
            semester = Semester.objects.create(name=extracted_semester_name, is_active=True)
            created = True

        if semester.is_active is not True:
            semester.is_active = True
            semester.save(update_fields=["is_active"])
        Semester.objects.filter(is_active=True).exclude(id=semester.id).update(is_active=False)
                
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

            linked_rooms = link_session_to_venue_parts(session, venue_parts)
            linked = len(linked_rooms)
            for room_obj in linked_rooms:
                response_data.append({
                    **s,
                    'linked_room': room_obj.name,
                    'building': room_obj.building.code if room_obj.building else derive_building_code(room_obj.name),
                })

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
            "semester": {"id": semester.id, "name": semester.name, "is_active": semester.is_active, "created": created},
            "data": response_data,
        })


@api_view(['GET'])
def health_check(request):
    return Response({"status": "ok"}, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter('semester', int, description='Filter by semester id'),
            OpenApiParameter('day', str, description='Filter by day of week (e.g. Monday)'),
            OpenApiParameter('course_code', str, description='Case-insensitive match on course code'),
            OpenApiParameter('room', str, description='Case-insensitive match on linked room name'),
            OpenApiParameter('page', int, description='Page number (page_size=10)'),
        ],
        responses={200: ClassSessionAdminSerializer(many=True)},
    ),
    create=extend_schema(request=ClassSessionAdminSerializer, responses={201: ClassSessionAdminSerializer}),
    retrieve=extend_schema(responses={200: ClassSessionAdminSerializer}),
    update=extend_schema(request=ClassSessionAdminSerializer, responses={200: ClassSessionAdminSerializer}),
    partial_update=extend_schema(request=ClassSessionAdminSerializer, responses={200: ClassSessionAdminSerializer}),
    destroy=extend_schema(responses={204: None}),
)
class AdminSessionViewSet(viewsets.ModelViewSet):
    """Admin-only CRUD for ClassSessions to correct extraction mistakes.

    Editing `raw_venue_text` (or setting it on create) automatically
    re-normalizes venues and re-syncs Building/Room/SessionRoom links
    using the same pipeline as timetable upload (so FL vs GD stays distinct).
    """

    serializer_class = ClassSessionAdminSerializer
    permission_classes = [IsAdminUser]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    pagination_class = AdminSessionPagination

    def get_queryset(self):
        qs = (
            ClassSession.objects.select_related('semester')
            .prefetch_related('rooms__building')
            .all()
            .order_by('day_of_week', 'start_time', 'id')
        )
        semester = self.request.query_params.get('semester')
        day = self.request.query_params.get('day')
        course_code = self.request.query_params.get('course_code')
        room = self.request.query_params.get('room')
        if semester:
            qs = qs.filter(semester_id=semester)
        if day:
            qs = qs.filter(day_of_week__iexact=day)
        if course_code:
            qs = qs.filter(course_code__icontains=course_code)
        if room:
            qs = qs.filter(rooms__name__icontains=room)
        return qs.distinct()

    def _sync_rooms(self, session, raw_venue_text, is_new=False):
        if raw_venue_text is None and not is_new:
            return
        try:
            sync_session_rooms_from_raw(session, raw_venue_text or '')
        except ValueError as e:
            if is_new:
                session.delete()
            raise serializers.ValidationError({"raw_venue_text": str(e)})

    def perform_create(self, serializer):
        if 'semester' not in serializer.validated_data:
            raise serializers.ValidationError(
                {"semester": "semester id is required."}
            )
        session = serializer.save()
        self._sync_rooms(session, serializer.validated_data.get('raw_venue_text'), is_new=True)

    def perform_update(self, serializer):
        session = serializer.save()
        if 'raw_venue_text' in serializer.validated_data:
            self._sync_rooms(session, serializer.validated_data.get('raw_venue_text'))
