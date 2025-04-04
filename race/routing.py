from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path("ws/pitlanes/<int:pitlane_number>/", consumers.ChangeLaneConsumer.as_asgi()),
    path("ws/changedriver/", consumers.ChangeDriverConsumer.as_asgi()),
    path("ws/roundpause/<int:round_id>/", consumers.RoundPauseConsumer.as_asgi()),
]
