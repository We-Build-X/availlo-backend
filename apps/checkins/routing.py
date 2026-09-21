from django.urls import re_path

from .consumers import RoomVotesConsumer

websocket_urlpatterns = [
    re_path(r"^ws/rooms/(?P<slug>[-\w]+)/votes/$", RoomVotesConsumer.as_asgi()),
]
