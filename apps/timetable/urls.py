from django.urls import path
from .views import UploadTimetableView

urlpatterns = [
    path('timetable/upload/', UploadTimetableView.as_view(), name='timetable-upload'),
]