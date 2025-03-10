from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import ChangeLane
from django.template.loader import render_to_string

@receiver(post_save, sender=ChangeLane)
def change_lane_updated(sender, instance, **kwargs):
    channel_layer = get_channel_layer()
    lane_html = render_to_string('layout/changelane_info.html', {'change_lane': instance})
    async_to_sync(channel_layer.group_send)(
        f'lane_{instance.lane}', #Use instance.lane
        {
            'type': 'lane.update',
            'lane_html': lane_html,
        }
    )
