from django.urls import path
from .views import (
    FreeRoomList, RoomListView, RoomStatusView,
    SearchRoomView, OccupiedRoomView, EndingSoonView,
    RoomDetailView, RoomDailyTimetableView,
)

urlpatterns = [
    path('rooms/', RoomListView.as_view(), name='room-list'),
    path('rooms/free/', FreeRoomList.as_view(), name='free-rooms'),
    path('rooms/occupied/', OccupiedRoomView.as_view(), name='occupied-rooms'),
    path('rooms/ending-soon/', EndingSoonView.as_view(), name='ending-soon-rooms'),
    path('rooms/<int:room_id>/status/', RoomStatusView.as_view(), name='room-status'),
    path('rooms/<slug:slug>/', RoomDetailView.as_view(), name='room-detail'),
    path('rooms/<slug:slug>/timetable/', RoomDailyTimetableView.as_view(), name='room-daily-timetable'),
    path('search/', SearchRoomView.as_view(), name='search-rooms'),
]