import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import ChangeLane
from django.template.loader import render_to_string

class ChangeLaneConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.lane_number = self.scope['url_route']['kwargs']['pitlane_number']
        self.lane_group_name = f'lane_{self.lane_number}'

        await self.channel_layer.group_add(
            self.lane_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.lane_group_name,
            self.channel_name
        )

    async def lane_update(self, event):
        lane_html = event['lane_html']
        await self.send(text_data=json.dumps({'lane_html': lane_html}))



class ChangeDriverConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.driverc_group_name = 'driverchange'

        await self.channel_layer.group_add(
            self.driverc_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.driverc_group_name,
            self.channel_name
        )

    async def lane_update(self, event):
        driverc_html = event['driverc_html']
        await self.send(text_data=json.dumps({'driverc_html': driverc_html}))


