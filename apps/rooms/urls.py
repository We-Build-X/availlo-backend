from django.urls import path
from rest_framework.routers import SimpleRouter
from rest_framework.authtoken.views import obtain_auth_token
from .views import (
    FreeRoomList, RoomListView, RoomStatusView,
    SearchRoomView, OccupiedRoomView, EndingSoonView,
    RoomDetailView, RoomDailyTimetableView,
    AdminRoomViewSet,
)

router = SimpleRouter(trailing_slash=True)
router.register(r'admin/rooms', AdminRoomViewSet, basename='admin-room')

urlpatterns = [
    path('rooms/', RoomListView.as_view(), name='room-list'),
    path('rooms/free/', FreeRoomList.as_view(), name='free-rooms'),
    path('rooms/occupied/', OccupiedRoomView.as_view(), name='occupied-rooms'),
    path('rooms/ending-soon/', EndingSoonView.as_view(), name='ending-soon-rooms'),
    path('rooms/<int:room_id>/status/', RoomStatusView.as_view(), name='room-status'),
    path('rooms/<slug:slug>/', RoomDetailView.as_view(), name='room-detail'),
    path('rooms/<slug:slug>/timetable/', RoomDailyTimetableView.as_view(), name='room-daily-timetable'),
    path('search/', SearchRoomView.as_view(), name='search-rooms'),
    path('auth/token/', obtain_auth_token, name='api-token-auth'),
]

urlpatterns += router.urls