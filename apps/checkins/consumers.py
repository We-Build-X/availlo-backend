import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

ROOM_VOTES_GROUP = "room_votes_{slug}"


def _group_name(slug):
    return ROOM_VOTES_GROUP.format(slug=slug)


class RoomVotesConsumer(AsyncWebsocketConsumer):
    """Push live vote counts for one room.

    Connect:  ws(s)://<host>/ws/rooms/<slug>/votes/
    Messages: JSON {"room", "occupied", "free", "total"}
      - one snapshot on connect
      - one broadcast every time a vote is POSTed for the room
    Votes are still submitted via POST /api/rooms/<slug>/vote/
    (WS is push-only; inbound messages are ignored except ping).
    """

    async def connect(self):
        self.slug = self.scope["url_route"]["kwargs"]["slug"]
        room = await self._get_room(self.slug)
        if room is None:
            await self.close(code=4404)
            return
        self.group = _group_name(self.slug)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps(await self._counts(room)))

    async def disconnect(self, close_code):
        group = getattr(self, "group", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        # Keep-alive pings only; voting goes through the REST endpoint.
        if text_data == "ping":
            await self.send(text_data="pong")

    async def votes_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    @staticmethod
    @database_sync_to_async
    def _get_room(slug):
        from apps.rooms.models import Room

        return Room.objects.filter(slug=slug).first()

    @staticmethod
    @database_sync_to_async
    def _counts(room):
        # Import here to avoid a hard import cycle at module load.
        from apps.checkins.views import get_vote_counts

        return {"room": room.slug, **get_vote_counts(room)}
