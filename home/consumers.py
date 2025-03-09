# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import async_to_sync

class ChangeLaneConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.changelane_id = self.scope['url_route']['kwargs']['changelane_id']
        self.changelane_group_name = f'changelane_{self.changelane_id}'

        await self.channel_layer.group_add(
            self.changelane_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.changelane_group_name,
            self.channel_name
        )

    async def send_changelane_update(self, event):
        changelane = event['changelane']
        await self.send(text_data=json.dumps(changelane))
