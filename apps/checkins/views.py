from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Count, Q

from apps.rooms.models import Room
from .models import CheckIn


VOTE_OCCUPIED = "occupied"
VOTE_FREE = "free"
VALID_VOTES = (VOTE_OCCUPIED, VOTE_FREE)


def get_vote_counts(room):
    """Return {'occupied': int, 'free': int, 'total': int} for a room."""
    agg = CheckIn.objects.filter(room=room).aggregate(
        occupied=Count("id", filter=Q(is_free=False)),
        free=Count("id", filter=Q(is_free=True)),
    )
    occupied = agg["occupied"] or 0
    free = agg["free"] or 0
    return {"occupied": occupied, "free": free, "total": occupied + free}


def vote_to_is_free(vote):
    return True if vote == VOTE_FREE else False


def is_free_to_vote(is_free):
    return VOTE_FREE if is_free else VOTE_OCCUPIED


def broadcast_vote_counts(room_slug, payload):
    """Push fresh counts to WS subscribers of this room. Best-effort."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            f"room_votes_{room_slug}",
            {"type": "votes.update", "data": {"room": room_slug, **payload}},
        )
    except Exception:
        # Never break the REST vote path because push failed.
        pass


class VoteRequestSerializer(serializers.Serializer):
    vote = serializers.ChoiceField(choices=VALID_VOTES)
    voter_key = serializers.CharField(max_length=100)


class RoomVoteView(APIView):
    """Submit (or change) a crowdsourced status vote for a room.

    One active vote per (room, voter_key) — enforced by the
    CheckIn unique_together and implemented via update_or_create,
    so re-voting updates the existing row instead of double-counting.
    """

    @extend_schema(
        request=VoteRequestSerializer,
        responses={
            200: inline_serializer(
                name="RoomVoteResponse",
                fields={
                    "room": serializers.CharField(),
                    "user_vote": serializers.ChoiceField(choices=VALID_VOTES),
                    "occupied": serializers.IntegerField(),
                    "free": serializers.IntegerField(),
                    "total": serializers.IntegerField(),
                },
            ),
        },
    )
    def post(self, request, slug):
        try:
            room = Room.objects.get(slug=slug)
        except Room.DoesNotExist:
            return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = VoteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        vote = serializer.validated_data["vote"]
        voter_key = serializer.validated_data["voter_key"].strip()
        if not voter_key:
            return Response(
                {"voter_key": ["This field may not be blank."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        CheckIn.objects.update_or_create(
            room=room,
            session_key=voter_key,
            defaults={"is_free": vote_to_is_free(vote)},
        )

        counts = get_vote_counts(room)
        broadcast_vote_counts(room.slug, counts)
        return Response(
            {"room": room.slug, "user_vote": vote, **counts},
            status=status.HTTP_200_OK,
        )


class RoomVotesView(APIView):
    """Fetch current crowdsourced vote counts for a room.

    Poll this endpoint (e.g. every 10-15s) for near-real-time updates.
    Pass ?voter_key=<key> to also get the caller's current vote.
    """

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="voter_key",
                description="Caller voter key to resolve their current vote",
                required=False,
                type=str,
            ),
        ],
        responses={
            200: inline_serializer(
                name="RoomVotesResponse",
                fields={
                    "room": serializers.CharField(),
                    "occupied": serializers.IntegerField(),
                    "free": serializers.IntegerField(),
                    "total": serializers.IntegerField(),
                    "user_vote": serializers.CharField(required=False, allow_null=True),
                },
            ),
        },
    )
    def get(self, request, slug):
        try:
            room = Room.objects.get(slug=slug)
        except Room.DoesNotExist:
            return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)

        counts = get_vote_counts(room)
        data = {"room": room.slug, **counts}

        voter_key = request.query_params.get("voter_key")
        if voter_key:
            checkin = CheckIn.objects.filter(room=room, session_key=voter_key).first()
            data["user_vote"] = is_free_to_vote(checkin.is_free) if checkin else None

        return Response(data, status=status.HTTP_200_OK)
