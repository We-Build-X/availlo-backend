from django.db import models
from apps.rooms.models import Room

SOURCE_CHOICES = [
    ('timetable', 'Timetable'),
    ('check-in', 'Check-In'),

]
CONFIDENCE_LEVELS = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
]

class CheckIn(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='checkins')
    is_free = models.BooleanField(default=True) #(True if the room is free, False if occupied)
    timestamp = models.DateTimeField(auto_now_add=True) #(when the check-in was made)
    session_key = models.CharField(max_length=100, null=True,blank=True) #To loosely identify the user, no login required

    class Meta:
        unique_together = (('room', 'session_key'),)  # Ensure one check-in per room per session_key

class RoomStatus(models.Model):
    room = models.OneToOneField(Room, on_delete=models.CASCADE, related_name='statuses')
    is_free = models.BooleanField(default=True) #(True if the room is free, False if occupied)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES) #(e.g., "timetable", "check-in")
    last_updated = models.DateTimeField(auto_now=True) #(when the status was last updated)
    confidence_level = models.CharField(choices=CONFIDENCE_LEVELS, max_length=20, null=True) #(confidence level)