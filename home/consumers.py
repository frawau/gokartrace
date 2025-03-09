# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import async_to_sync
from .models import ChangeLane

class ChangeLaneConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        changelane_number = self.scope['url_route']['kwargs']['changelane_number']
        try:
            changelane = await self.get_changelane(changelane_number)
            self.changelane_group_name = f'changelane_{changelane.id}' #Use ID for channel group
        except ChangeLane.DoesNotExist:
            await self.close()
            return

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

    async def get_changelane(self, number):
        return await ChangeLane.objects.aget(number=number)
