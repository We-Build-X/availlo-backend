from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import RoomSerializer
from .status_engine import get_room_status
from datetime import datetime
from .models import Room



class RoomListView(APIView):
    def get(self, request):
        rooms = Room.objects.select_related('building').all()
        serializer = RoomSerializer(rooms, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class RoomStatusView(APIView):
    def get(self, request, room_id):
        try:
            room = Room.objects.select_related('building').get(id=room_id)
        except Room.DoesNotExist:
            return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)
        
        room_status = get_room_status(room, datetime.now())
        
        return Response(room_status, status=status.HTTP_200_OK)
    
# get free room and also enable filtering free rooms by building
class FreeRoomList(APIView):
    def get(self, request):
        building_code = request.query_params.get('building', None)
        rooms = Room.objects.select_related('building').all()
        if building_code:
            rooms =rooms.filter(building__code=building_code.upper())

        free_rooms = []
        for room in rooms:
            room_status = get_room_status(room, datetime.now())
            if room_status.get("is_free"):
                free_rooms.append({
                    "id": room.id,
                    "name": room.name,
                    "building": room.building.name if room.building else None,
                    "capacity": room.capacity,
                    "next_session": room_status.get("next_session")
                })
            
        return Response(free_rooms, status=status.HTTP_200_OK)

class SearchRoomView(APIView):
    def get(self, request):
        query = request.query_params.get('q', '')
        rooms = Room.objects.filter(name__icontains=query).select_related('building')
        serializer = RoomSerializer(rooms, many=True)

        for room in rooms:
            room_status = get_room_status(room, datetime.now())
            room_data = next((item for item in serializer.data if item["id"] == room.id), None)
            if room_data:
                room_data["is_free"] = room_status.get("is_free")
                room_data["next_session"] = room_status.get("next_session")


        return Response(serializer.data, status=status.HTTP_200_OK)
    
#CREATE ENDPOINT FOR THIS.. REMEMBER