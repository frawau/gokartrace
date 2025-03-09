from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('changelanes/<int:changelane_number>/', consumers.ChangeLaneConsumer.as_asgi()),
]
