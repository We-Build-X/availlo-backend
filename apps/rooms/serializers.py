from rest_framework.serializers import ModelSerializer
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