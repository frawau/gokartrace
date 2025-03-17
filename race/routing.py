from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/pitlanes/<int:pitlane_number>/', consumers.ChangeLaneConsumer.as_asgi()),
    path('ws/driverchange/', consumers.ChangeDriverConsumer.as_asgi()),
]
