from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import ChangeLane, round_pause, team_member, round_team, Round, Session
from django.template.loader import render_to_string
from django.db.models import Count

# Function to update all connected clients
def update_empty_teams(round_id):
    # Get the channel layer
    channel_layer = get_channel_layer()

    # Get the current empty teams
    teams_without_members = list(
        round_team.objects.filter(round_id=round_id)
        .annotate(member_count=Count("team_member"))
        .filter(member_count=0)
        .select_related("team__championship", "team__team")
    )

    # Format the teams data
    empty_teams = [
        {
            "id": rt.id,
            "team_name": rt.team.team.name,
            "number": rt.team.number,
            "championship_name": rt.team.championship.name,
        }
        for rt in teams_without_members
    ]

    # Send update to the room group
    async_to_sync(channel_layer.group_send)(
        f"empty_teams_{round_id}", {"type": "empty_teams_list", "teams": empty_teams}
    )


# Listen for team member changes
@receiver([post_save, post_delete], sender=team_member)
def team_member_changed(sender, instance, **kwargs):
    """Called when a team member is added, changed or deleted"""
    # Get the round ID from the team
    round_id = instance.team.round_id

    # Update empty teams for this round
    update_empty_teams(round_id)


# Listen for round team changes
@receiver([post_save, post_delete], sender=round_team)
def round_team_changed(sender, instance, **kwargs):
    """Called when a round team is added, changed or deleted"""
    # Update empty teams for this round
    update_empty_teams(instance.round_id)


@receiver(post_save, sender=ChangeLane)
def change_lane_updated(sender, instance, created, **kwargs):
    if not created:  # Only send updates if the instance was modified
        channel_layer = get_channel_layer()
        lane_html = render_to_string(
            "layout/changelane_detail.html", {"change_lane": instance}
        )
        async_to_sync(channel_layer.group_send)(
            f"lane_{instance.lane}",
            {
                "type": "lane.update",
                "lane_html": lane_html,
            },
        )

        lane_html = render_to_string(
            "layout/changelane_small_detail.html", {"change_lane": instance}
        )
        async_to_sync(channel_layer.group_send)(
            f"lane_{instance.lane}",
            {
                "type": "rclane.update",
                "lane_html": lane_html,
            },
        )

        change_lanes = ChangeLane.objects.filter(open=True).order_by("lane")
        driverc_html = render_to_string(
            "layout/changedriver_detail.html", {"change_lanes": change_lanes}
        )

        async_to_sync(channel_layer.group_send)(
            "changedriver",
            {
                "type": "changedriver.update",
                "driverc_html": driverc_html,
            },
        )


@receiver(post_delete, sender=ChangeLane)
def change_lane_deleted(sender, instance, **kwargs):
    # Add logic here if you want to send a websocket message when a lane is deleted.
    pass


@receiver(post_save, sender=round_pause)
def handle_pause_change(sender, instance, **kwargs):
    cround = instance.round
    is_paused = cround.is_paused
    is_ready = cround.ready
    started = cround.started != None
    ended = cround.ended != None
    remaining = round(cround.duration - round(cround.time_elapsed).total_seconds())

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"round_{round.id}",
        {
            "type": "pause_update",
            "is paused": is_paused,
            "remaining seconds": remaining,
            "started": started,
            "ready": is_ready,
            "ended": ended,
        },
    )


@receiver(post_save, sender=Round)
def handle_round_change(sender, instance, **kwargs):
    """Handle round state changes (started, ended) for timer updates"""
    is_paused = instance.is_paused
    is_ready = instance.ready
    started = instance.started != None
    ended = instance.ended != None
    remaining = round(
        (instance.duration - instance.time_elapsed).total_seconds()
        if instance.started
        else instance.duration.total_seconds()
    )

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"round_{instance.id}",
        {
            "type": "round_update",
            "is paused": is_paused,
            "remaining seconds": remaining,
            "started": started,
            "ready": is_ready,
            "ended": ended,
        },
    )


@receiver(post_save, sender=Session)
def handle_session_change(sender, instance, **kwargs):
    """Handle session changes for driver timer updates"""
    round_instance = instance.round
    driver = instance.driver
    if instance.end:
        dstatus = "end"
    elif instance.start:
        dstatus = "start"
    elif instance.register:
        dstatus = "register"
    else:
        dstatus = "reset"

    channel_layer = get_channel_layer()
    # First update the round timer
    async_to_sync(channel_layer.group_send)(
        f"round_{round_instance.id}",
        {
            "type": "session_update",
            "is paused": round_instance.is_paused,
            "time spent": round(driver.time_spent.total_seconds()),
            "driver id": driver.id,
            "driver status": dstatus,
        },
    )


@receiver(pre_delete, sender=Session)
def handle_session_delete(sender, instance, **kwargs):
    round_instance = instance.round
    driver = instance.driver
    dstatus = "reset"
    channel_layer = get_channel_layer()
    # First update the round timer
    async_to_sync(channel_layer.group_send)(
        f"round_{round_instance.id}",
        {
            "type": "session_update",
            "is paused": round_instance.is_paused,
            "time spent": round(driver.time_spent.total_seconds()),
            "driver id": driver.id,
            "driver status": dstatus,
        },
    )
