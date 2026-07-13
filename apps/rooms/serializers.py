from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import Building, Room
from .status_engine import get_room_status
from datetime import datetime
from zoneinfo import ZoneInfo

class BuildingSerializer(ModelSerializer):
    class Meta:
        model = Building
        fields = ['id', 'name', 'code']

class RoomSerializer(ModelSerializer):
    building = BuildingSerializer(read_only=True)

    class Meta:
        model = Room
        fields = ['id', 'name', 'building', 'capacity']

class SessionPayloadSerializer(serializers.Serializer):
    course_code = serializers.CharField()
    start_time = serializers.CharField()
    end_time = serializers.CharField()
    level = serializers.CharField(allow_null=True, required=False)
    group = serializers.CharField(allow_null=True, required=False)

class FreeRoomSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(max_length=100)
    building = BuildingSerializer()
    capacity = serializers.IntegerField()
    next_session = SessionPayloadSerializer(allow_null=True, required=False)

class TimetableEntrySerializer(serializers.Serializer):
    start_time = serializers.CharField()
    end_time = serializers.CharField()
    course_title = serializers.CharField(allow_null=True)
    is_class = serializers.BooleanField()


class RoomDetailSerializer(ModelSerializer):
    building = BuildingSerializer(read_only=True)
    status = serializers.SerializerMethodField()
    free_until = serializers.SerializerMethodField()
    next_available_time = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = [
            'id', 'slug', 'name', 'building', 'capacity',
            'has_power', 'image',
            'status', 'free_until', 'next_available_time',
        ]

    def get_status(self, obj):
        data = self.context.get('room_status', {})
        return data.get('status') if 'error' not in data else None

    def get_free_until(self, obj):
        data = self.context.get('room_status', {})
        return data.get('free_until') if 'error' not in data else None

    def get_next_available_time(self, obj):
        data = self.context.get('room_status', {})
        return data.get('next_available_time') if 'error' not in data else None