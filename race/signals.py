from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import ChangeLane, round_pause
from django.template.loader import render_to_string


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
    round = instance.round
    is_paused = round.round_pause_set.filter(end__isnull=True).exists()
    remaining = (round.duration - round.time_elapsed).total_seconds()

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"roundpause_{round.id}",
        {
            "type": "round_update",
            "is_paused": is_paused,
            "remaining_seconds": remaining,
        },
    )
