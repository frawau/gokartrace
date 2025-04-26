import asyncio
import json
import datetime as dt
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import ChangeLane, round_team, team_member, championship_team, Round
from django.template.loader import render_to_string
from channels.db import database_sync_to_async
from django.db.models import Count, Q

# Import your models


class EmptyTeamsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Get the current round
        self.current_round = await self.get_current_round()

        if not self.current_round:
            # No active round found, close connection
            await self.close(code=4000)
            return

        self.round_id = self.current_round.id
        self.room_group_name = f"empty_teams_{self.round_id}"

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

        # Send initial empty teams list
        empty_teams = await self.get_empty_teams(self.round_id)
        await self.send(
            text_data=json.dumps({"type": "empty_teams_list", "teams": empty_teams})
        )

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Receive message from WebSocket
    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get("action")

        if action == "delete_empty_teams":
            # Delete all empty teams for current round
            deleted_count = await self.delete_empty_teams(self.round_id)

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "system_message",
                    "message": f"Deleted {deleted_count} empty teams",
                    "tag": "success" if deleted_count > 0 else "info",
                },
            )

            # No need to broadcast empty teams list here
            # The signal handlers will automatically do it

        elif action == "delete_single_team":
            team_id = data.get("team_id")
            if team_id:
                success = await self.delete_single_team(team_id)

                # Send message to room group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "system_message",
                        "message": "Team deleted successfully"
                        if success
                        else "Failed to delete team",
                        "tag": "success" if success else "danger",
                    },
                )

                # No need to broadcast empty teams list here
                # The signal handlers will automatically do it

    # Receive message from room group
    async def empty_teams_list(self, event):
        # Send teams list to WebSocket
        await self.send(
            text_data=json.dumps({"type": "empty_teams_list", "teams": event["teams"]})
        )

    # Send system message
    async def system_message(self, event):
        # Send message to WebSocket
        await self.send(
            text_data=json.dumps(
                {
                    "type": "system_message",
                    "message": event["message"],
                    "tag": event["tag"],
                }
            )
        )

    # Database operations
    @database_sync_to_async
    def get_current_round(self):
        end_date = dt.date.today()
        start_date = end_date - dt.timedelta(days=1)
        return Round.objects.filter(
            Q(start__date__range=[start_date, end_date]) & Q(ended__isnull=True)
        ).first()

    @database_sync_to_async
    def get_empty_teams(self, round_id):
        teams_without_members = list(
            round_team.objects.filter(round_id=round_id)
            .annotate(member_count=Count("team_member"))
            .filter(member_count=0)
            .select_related("team__championship", "team__team")
        )

        return [
            {
                "id": rt.id,
                "team_name": rt.team.team.name,
                "number": rt.team.number,
                "championship_name": rt.team.championship.name,
            }
            for rt in teams_without_members
        ]

    @database_sync_to_async
    def delete_empty_teams(self, round_id):
        result = (
            round_team.objects.filter(round_id=round_id)
            .annotate(member_count=Count("team_member"))
            .filter(member_count=0)
            .delete()
        )

        # Return the count of deleted teams
        return result[0] if result else 0

    @database_sync_to_async
    def delete_single_team(self, team_id):
        try:
            rt = round_team.objects.get(id=team_id)
            if team_member.objects.filter(team=rt).count() == 0:
                rt.delete()
                return True
            return False
        except round_team.DoesNotExist:
            return False


class ChangeLaneConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.lane_number = self.scope["url_route"]["kwargs"]["pitlane_number"]
        self.lane_group_name = f"lane_{self.lane_number}"

        await self.channel_layer.group_add(self.lane_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.lane_group_name, self.channel_name)

    async def lane_update(self, event):
        lane_html = event["lane_html"]
        await self.send(
            text_data=json.dumps({"type": "lane.update", "lane_html": lane_html})
        )

    async def rclane_update(self, event):
        lane_html = event["lane_html"]
        await self.send(
            text_data=json.dumps({"type": "rclane.update", "lane_html": lane_html})
        )


class ChangeDriverConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.driverc_group_name = "changedriver"

        await self.channel_layer.group_add(self.driverc_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.driverc_group_name, self.channel_name
        )

    async def changedriver_update(self, event):
        driverc_html = event["driverc_html"]
        await self.send(text_data=json.dumps({"driverc_html": driverc_html}))


class RoundPauseConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.round_id = self.scope["url_route"]["kwargs"]["round_id"]
        self.round_group_name = f"roundpause_{self.round_id}"

        await self.channel_layer.group_add(self.round_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.round_group_name, self.channel_name)

    async def round_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "round_update",
                    "is_paused": event["is paused"],
                    "remaining_seconds": event["remaining seconds"],
                }
            )
        )


class RoundConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print("Round Consumer connection")
        self.round_id = self.scope["url_route"]["kwargs"]["round_id"]
        self.round_group_name = f"round_{self.round_id}"

        # Join room group
        await self.channel_layer.group_add(self.round_group_name, self.channel_name)

        await self.accept()
        print(f"Round Consumer connection to {self.round_group_name} accepted.")

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(self.round_group_name, self.channel_name)

    # Receive message from WebSocket
    async def receive(self, text_data):
        # We can handle client-to-server messages here if needed
        pass

    # Receive message from room group
    async def round_update(self, event):
        # Send message to WebSocket
        if event["type"] == "session update":
            await self.send(
                text_data=json.dumps(
                    {
                        "is_paused": event["is paused"],
                        "time_spent": event["time spent"],
                        "session_update": True,
                        "driver_id": event["driver_id"],
                        "driver_status": event["driver status"],
                    }
                )
            )
        else:
            await self.send(
                text_data=json.dumps(
                    {
                        "is_paused": event["is_paused"],
                        "remaining_seconds": event["remaining_seconds"],
                        "session_update": False,
                    }
                )
            )
