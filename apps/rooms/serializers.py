from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import Building, Room

class BuildingSerializer(ModelSerializer):
    class Meta:
        model = Building
        fields = ['id', 'name', 'code']

class RoomSerializer(ModelSerializer):
    building = BuildingSerializer(read_only=True)

    class Meta:
        model = Room
        fields = ['id', 'name', 'building', 'capacity']

class FreeRoomSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(max_length=100)
    building = BuildingSerializer()
    capacity = serializers.IntegerField()
    next_session = serializers.DateTimeField(allow_null=True, required=False)