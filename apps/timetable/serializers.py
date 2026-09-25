from rest_framework import serializers
from .models import ClassSession, Semester


class LinkedRoomSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    building_code = serializers.CharField(read_only=True, allow_null=True)


class ClassSessionAdminSerializer(serializers.ModelSerializer):
    semester = serializers.PrimaryKeyRelatedField(
        queryset=Semester.objects.all(), required=False
    )
    rooms = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ClassSession
        fields = [
            'id', 'semester', 'course_code', 'day_of_week',
            'start_time', 'end_time', 'level', 'group',
            'raw_venue_text', 'rooms',
        ]
        read_only_fields = ['id', 'rooms']

    def get_rooms(self, obj):
        rooms = getattr(obj, 'prefetched_rooms', None)
        if rooms is None:
            rooms = obj.rooms.select_related('building').all()
        return [
            {
                'id': r.id,
                'name': r.name,
                'building_code': r.building.code if r.building else None,
            }
            for r in rooms
        ]

    def validate(self, attrs):
        start = attrs.get('start_time', getattr(self.instance, 'start_time', None))
        end = attrs.get('end_time', getattr(self.instance, 'end_time', None))
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_time": "end_time must be after start_time."}
            )
        return attrs
