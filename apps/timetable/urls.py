from django.urls import path
from .views import UploadTimetableView,health_check

urlpatterns = [
    path('timetable/upload/', UploadTimetableView.as_view(), name='timetable-upload'),
    path('health/', health_check, name='health-check'),

]