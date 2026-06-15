from django.urls import path
from .views import FreeRoomList, RoomListView, RoomStatusView, SearchRoomView, OccupiedRoomView, EndingSoonView

urlpatterns = [
    path('rooms/', RoomListView.as_view(), name='room-list'),
    path('rooms/free/', FreeRoomList.as_view(), name='free-rooms'),    
    path('rooms/<int:room_id>/status/', RoomStatusView.as_view(), name='room-status'), 
    path('search/', SearchRoomView.as_view(), name='search-rooms'),
    path('rooms/occupied/', OccupiedRoomView.as_view(), name='occupied-rooms'),
    path('rooms/ending-soon/', EndingSoonView.as_view(), name='ending-soon-rooms'),
]