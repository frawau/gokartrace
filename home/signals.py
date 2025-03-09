# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ChangeLane
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .serializers import ChangeLaneSerializer

@receiver(post_save, sender=ChangeLane)
def changelane_updated(sender, instance, **kwargs):
    """
    Sends a WebSocket message when a ChangeLane instance is saved.
    """
    channel_layer = get_channel_layer()
    serializer = ChangeLaneSerializer(instance)
    changelane_data = serializer.data

    try:
        async_to_sync(channel_layer.group_send)(
            f'changelane_{instance.id}',  # Group name based on ChangeLane ID
            {
                'type': 'send.changelane.update',
                'changelane': changelane_data,
            },
        )
    except:
        pass
