from django.db import models
from apps.rooms.models import Room, Building
DAYS_OF_WEEK = [
    ('Monday', 'Monday'),
    ('Tuesday', 'Tuesday'),
    ('Wednesday', 'Wednesday'),
    ('Thursday', 'Thursday'),
    ('Friday', 'Friday'),
]

LEVEL_CHOICES = [
    ('100 Level', '100 Level'),
    ('200 Level', '200 Level'),
    ('300 Level', '300 Level'),
    ('400 Level', '400 Level'),
    ('500 Level', '500 Level'),
]

class Semester(models.Model):
    name = models.CharField(max_length=100) #(e.g., "2025/2026 Second Semester")
    is_active = models.BooleanField(default=True) #(to indicate the current active semester)

    def __str__(self):
        return self.name
    
    
class ClassSession(models.Model):
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='class_sessions')
    course_code = models.CharField(max_length=20)  # (e.g., "CSC101")
    day_of_week = models.CharField(max_length=20, choices=DAYS_OF_WEEK)  # (e.g., "Monday")
    # A session may be assigned to multiple rooms; use a many-to-many through table below
    rooms = models.ManyToManyField(Room, through='SessionRoom', related_name='class_sessions')
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, null=True, blank=True)  # (e.g., "100 Level")
    group = models.CharField(max_length=20, null=True, blank=True)  # (e.g., "Group I")
    start_time = models.TimeField()  # (e.g., 09:00)
    end_time = models.TimeField()  # (e.g., 10:30)

    raw_venue_text = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            # Matches the status-engine filter: semester + day_of_week, then
            # ordering/filtering by start_time.
            models.Index(fields=['semester', 'day_of_week', 'start_time']),
        ]

    def __str__(self):
        return f"{self.course_code} - ({self.semester.name})"


class SessionRoom(models.Model):
    class_session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name='session_rooms')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='session_rooms')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('class_session', 'room')
        indexes = [
            models.Index(fields=['room']),
            # Composite index matching the status engine query:
            # WHERE room_id IN (...) JOIN class_session ON class_session_id = ...
            models.Index(fields=['room', 'class_session']),
        ]