from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('changelanes/<int:changelane_lane>/', consumers.ChangeLaneConsumer.as_asgi()),
]
