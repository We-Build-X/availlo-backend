from django.urls import path
from .views import RoomVoteView, RoomVotesView

urlpatterns = [
    path('rooms/<slug:slug>/vote/', RoomVoteView.as_view(), name='room-vote'),
    path('rooms/<slug:slug>/votes/', RoomVotesView.as_view(), name='room-votes'),
]
