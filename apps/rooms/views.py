from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import RoomSerializer, FreeRoomSerializer, RoomDetailSerializer, TimetableEntrySerializer
from apps.timetable.models import ClassSession, Semester
from datetime import time
from .status_engine import get_room_status, get_rooms_status_bulk
from datetime import datetime
from .models import Room
from drf_spectacular.utils import extend_schema, OpenApiParameter
from zoneinfo import ZoneInfo
from rest_framework.pagination import PageNumberPagination





class SetPagination(PageNumberPagination):
    page_size = 10
    

class RoomListView(APIView):
    @extend_schema(
        responses={200: RoomSerializer(many=True)}
    )
    def get(self, request):
        rooms = Room.objects.select_related('building').all()
        serializer = RoomSerializer(rooms, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class RoomStatusView(APIView):
    @extend_schema(
        responses={200: RoomSerializer}
    )
    def get(self, request, room_id):
        try:
            room = Room.objects.select_related('building').get(id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)
        
        room_status = get_room_status(room, datetime.now(ZoneInfo("Africa/Lagos")))
        
        return Response(room_status, status=status.HTTP_200_OK)
    
# get free room and also enable filtering free rooms by building
class FreeRoomList(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(name='building', description='Filter free rooms by building code (e.g. "ENG" for Engineering Building)', required=False, type=str)
        ],
        responses={
            200: RoomSerializer(many=True),
            404: OpenApiParameter(name='error', description='Error message if no rooms found', type=str),
            
            }
    )
    def get(self, request):
        building_code = request.query_params.get('building', None)
        rooms = Room.objects.select_related('building').all()
        paginator = SetPagination()
        
        

        if building_code:
            rooms =rooms.filter(building__code=building_code.upper())

        rooms = list(rooms)
        statuses = get_rooms_status_bulk(rooms, datetime.now(ZoneInfo("Africa/Lagos")))

        free_rooms = []
        for room in rooms:
            room_status = statuses[room.id]
            if room_status.get("is_free"):
                free_rooms.append({
                    "id": room.id,
                    "name": room.name,
                    "building":{
                            "id": room.building.id if room.building else None,
                            "name": room.building.name if room.building else None,
                            "code": room.building.code if room.building else None

                    },
                    "capacity": room.capacity,
                    "next_session": room_status.get("next_session")
                })
        page =paginator.paginate_queryset(free_rooms, request)

        serializer = FreeRoomSerializer(page, many=True)
            
        return paginator.get_paginated_response(serializer.data)

class SearchRoomView(APIView):
    @extend_schema(
            parameters=[
                OpenApiParameter(name='q', description='Search query for room name', required=False, type=str)
            ],
            responses={
                200: RoomSerializer(many=True),
                404: OpenApiParameter(name='error', description='Error message if no rooms found', type=str),
                
            }
    )
    def get(self, request):
        query = request.query_params.get('q', '')
        rooms = list(Room.objects.filter(name__icontains=query).select_related('building'))
        serializer = RoomSerializer(rooms, many=True)
        pagination_class = SetPagination()

        statuses = get_rooms_status_bulk(rooms, datetime.now(ZoneInfo("Africa/Lagos")))
        for room in rooms:
            room_status = statuses[room.id]
            room_data = next((item for item in serializer.data if item["id"] == room.id), None)
            if room_data:
                room_data["is_free"] = room_status.get("is_free")
                room_data["next_session"] = room_status.get("next_session")

        page = pagination_class.paginate_queryset(serializer.data, request)
        return pagination_class.get_paginated_response(page)
    

    

class OccupiedRoomView(APIView):
    @extend_schema(
        responses={200: RoomSerializer(many=True)}
    )
    def get(self, request):
        rooms = list(Room.objects.select_related('building').all())
        statuses = get_rooms_status_bulk(rooms, datetime.now(ZoneInfo("Africa/Lagos")))
        occupied_rooms = []
        for room in rooms:
            room_status = statuses[room.id]
            if not room_status.get("is_free"):
                occupied_rooms.append({
                    "id": room.id,
                    "name": room.name,
                    "building": {
                        "id": room.building.id if room.building else None,
                        "name": room.building.name if room.building else None,
                        "code": room.building.code if room.building else None
                    },
                    "capacity": room.capacity,
                    "current_session": room_status.get("current_session")
                })
            
        return Response(occupied_rooms, status=status.HTTP_200_OK)
    

class EndingSoonView(APIView):
    @extend_schema(
        responses={200: RoomSerializer(many=True)}
    )
    def get(self, request):
        rooms = list(Room.objects.select_related('building').all())
        statuses = get_rooms_status_bulk(rooms, datetime.now(ZoneInfo("Africa/Lagos")))
        ending_soon_rooms = []
        for room in rooms:
            room_status = statuses[room.id]
            if not room_status.get("is_free") and room_status.get("current_session"):
                end_time_str = room_status["current_session"]["end_time"]
                end_time = datetime.strptime(end_time_str, "%H:%M").time()
                current_time = datetime.now(ZoneInfo("Africa/Lagos")).time()
                time_diff = (datetime.combine(datetime.today(), end_time) - datetime.combine(datetime.today(), current_time)).total_seconds() / 60
                if 0 < time_diff <= 15:  # Ending within the next 15 minutes
                    ending_soon_rooms.append({
                        "id": room.id,
                        "name": room.name,
                        "building": room.building.name if room.building else None,
                        "capacity": room.capacity,
                        "current_session": room_status.get("current_session"),
                        "minutes_until_free": int(time_diff)
                    })
            
        return Response(ending_soon_rooms, status=status.HTTP_200_OK)


class RoomDetailView(APIView):
    @extend_schema(
        responses={200: RoomDetailSerializer}
    )
    def get(self, request, slug):
        try:
            room = Room.objects.select_related('building').get(slug=slug)
        except Room.DoesNotExist:
            return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)

        room_status = get_room_status(room, datetime.now(ZoneInfo("Africa/Lagos")))
        serializer = RoomDetailSerializer(room, context={'room_status': room_status})
        return Response(serializer.data, status=status.HTTP_200_OK)


class RoomDailyTimetableView(APIView):
    DAY_START = time(7, 0)
    DAY_END = time(19, 0)

    @extend_schema(
        parameters=[
            OpenApiParameter(name='date', description='Date in YYYY-MM-DD format (defaults to today)', required=False, type=str),
        ],
        responses={200: TimetableEntrySerializer(many=True)},
    )
    def get(self, request, slug):
        try:
            room = Room.objects.get(slug=slug)
        except Room.DoesNotExist:
            return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)

        date_str = request.query_params.get('date')
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            target_date = datetime.now(ZoneInfo("Africa/Lagos")).date()

        day_name = target_date.strftime("%A")
        if day_name not in dict(ClassSession.DAYS_OF_WEEK):
            entries = [
                {
                    "start_time": self.DAY_START.strftime("%H:%M"),
                    "end_time": self.DAY_END.strftime("%H:%M"),
                    "course_title": None,
                    "is_class": False,
                }
            ]
            serializer = TimetableEntrySerializer(entries, many=True)
            return Response(serializer.data)

        active_semester = Semester.objects.filter(is_active=True).first()
        if not active_semester:
            return Response({"error": "No active semester found."}, status=status.HTTP_404_NOT_FOUND)

        sessions = ClassSession.objects.filter(
            semester=active_semester,
            day_of_week=day_name,
            session_rooms__room=room,
        ).order_by('start_time')

        entries = []
        prev_end = self.DAY_START

        for session in sessions:
            if prev_end < session.start_time:
                entries.append({
                    "start_time": prev_end.strftime("%H:%M"),
                    "end_time": session.start_time.strftime("%H:%M"),
                    "course_title": None,
                    "is_class": False,
                })

            entries.append({
                "start_time": session.start_time.strftime("%H:%M"),
                "end_time": session.end_time.strftime("%H:%M"),
                "course_title": session.course_code,
                "is_class": True,
            })
            prev_end = session.end_time

        if prev_end < self.DAY_END:
            entries.append({
                "start_time": prev_end.strftime("%H:%M"),
                "end_time": self.DAY_END.strftime("%H:%M"),
                "course_title": None,
                "is_class": False,
            })

        serializer = TimetableEntrySerializer(entries, many=True)
        return Response(serializer.data)