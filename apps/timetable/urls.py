from django.urls import path
from rest_framework.routers import SimpleRouter
from .views import UploadTimetableView, health_check, AdminSessionViewSet

router = SimpleRouter(trailing_slash=True)
router.register(r'admin/sessions', AdminSessionViewSet, basename='admin-session')

urlpatterns = [
    path('timetable/upload/', UploadTimetableView.as_view(), name='timetable-upload'),
    path('health/', health_check, name='health-check'),

]

urlpatterns += router.urls