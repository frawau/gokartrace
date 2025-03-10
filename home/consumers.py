import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

from .models import ChangeLane

class ChangeLaneConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.lane = self.scope['url_route']['kwargs']['lane']
        self.lane_group_name = f'changelane_{self.lane}'

        await self.channel_layer.group_add(
            self.lane_group_name,
            self.channel_name
        )

        await self.accept()
        await self.send_changelane_data()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.lane_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        await self.channel_layer.group_send(
            self.lane_group_name,
            {
                'type': 'changelane.message',
                'message': message
            }
        )

    async def changelane_message(self, event):
        message = event['message']

        await self.send(text_data=json.dumps({
            'message': message
        }))

    @sync_to_async
    def get_changelane_data(self, lane):
        # Récupérer les données de ChangeLane pour une voie spécifique
        changelanes = ChangeLane.objects.filter(lane=lane)
        data = [{'id': cl.id, 'lane': cl.lane, 'driver': str(cl.driver), 'open': cl.open} for cl in changelanes]
        return data

    async def send_changelane_data(self):
        data = await self.get_changelane_data(self.lane)
        await self.send(text_data=json.dumps({
            'type': 'changelane_data',
            'data': data
        }))
