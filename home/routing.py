from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('changelanes/<int:changelane_id>/', consumers.ChangeLaneConsumer.as_asgi()),
]
