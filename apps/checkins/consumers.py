import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

ROOM_VOTES_GROUP = "room_votes_{slug}"


def _group_name(slug):
    return ROOM_VOTES_GROUP.format(slug=slug)


class RoomVotesConsumer(AsyncWebsocketConsumer):
    """Push live vote counts for one room.

    Connect:  ws(s)://<host>/ws/rooms/<slug>/votes/
    Messages: JSON {"room", "occupied", "free", "total", "live"}
      - one snapshot on connect (always delivered, even if Redis is down)
      - one broadcast every time a vote is POSTed for the room
    "live" is False when the channel layer is unreachable: the client
    should fall back to polling GET /api/rooms/<slug>/votes/.
    Votes are still submitted via POST /api/rooms/<slug>/vote/
    (WS is push-only; inbound messages are ignored except ping).
    """

    async def connect(self):
        self.slug = self.scope["url_route"]["kwargs"]["slug"]
        room = await self._get_room(self.slug)
        if room is None:
            await self.close(code=4404)
            return
        # Accept FIRST so a broken channel layer can never kill the
        # handshake; the client still gets a usable snapshot.
        self.group = None
        await self.accept()
        live = await self._join_group()
        data = await self._counts(room)
        data["live"] = live
        await self.send(text_data=json.dumps(data))
        if not live:
            # Degraded mode: snapshot delivered. Close cleanly (1013 = try
            # again later) so the client falls back to REST polling instead
            # of holding a dead socket — the broken layer would otherwise
            # kill this connection with an application exception anyway.
            await self.close(code=1013)

    async def disconnect(self, close_code):
        group = getattr(self, "group", None)
        channel_layer = getattr(self, "channel_layer", None)
        if group and channel_layer is not None:
            try:
                await channel_layer.group_discard(group, self.channel_name)
            except Exception:
                logger.warning("group_discard failed for %s", group, exc_info=True)

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        # Keep-alive pings only; voting goes through the REST endpoint.
        if text_data == "ping":
            await self.send(text_data="pong")

    async def votes_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    async def _join_group(self):
        """Join the room broadcast group. Returns True if live push works."""
        group = _group_name(self.slug)
        try:
            await self.channel_layer.group_add(group, self.channel_name)
            self.group = group
            return True
        except Exception:
            logger.warning(
                "channel layer unavailable for %s; serving snapshot only",
                group,
                exc_info=True,
            )
            return False

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
