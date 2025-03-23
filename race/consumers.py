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

    async def rclane_update(self, event):
        lane_html = event['lane_html']
        await self.send(text_data=json.dumps({'lane_html': lane_html}))


class ChangeDriverConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.driverc_group_name = 'changedriver'

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

    async def changedriver_update(self, event):
        driverc_html = event['driverc_html']
        await self.send(text_data=json.dumps({'driverc_html': driverc_html}))


class RoundPauseConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.round_id = self.scope['url_route']['kwargs']['round_id']
        self.round_group_name = f'round_{self.round_id}'

        await self.channel_layer.group_add(
            self.round_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.round_group_name,
            self.channel_name
        )

    async def round_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'round_update',
            'is_paused': event['is_paused'],
            'remaining_seconds': event['remaining_seconds'],
        }))
