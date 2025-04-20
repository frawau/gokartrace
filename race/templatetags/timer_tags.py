# yourapp/templatetags/timer_tags.py
from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()

@register.simple_tag
def timer_widget(element_id, timer_type, instance=None, initial_value=0, show_hours=True, show_minutes=True):
    """
    Renders a timer widget.

    Args:
        element_id: HTML element ID
        timer_type: One of 'countdownDisplay', 'totaltime', or 'sessiontime'
        instance: The model instance (Round or team_member)
        initial_value: Initial value in seconds (optional)
        show_hours: Whether to show hours (default: True)
        show_minutes: Whether to show minutes (default: True)
    """
    if not instance:
        return mark_safe(f'<span id="{element_id}" class="timer">00:00:00</span>')

    # Default configuration
    config = {
        'elementId': element_id,
        'showHours': show_hours,
        'showMinutes': show_minutes,
        'timerType': timer_type
    }

    if timer_type == 'countdownDisplay':
        if hasattr(instance, 'duration'):  # Instance is a Round
            # Convert duration to seconds
            initial_seconds = instance.duration.total_seconds()
            remaining = (instance.duration - instance.time_elapsed).total_seconds() if instance.started else initial_seconds

            config.update({
                'startValue': remaining,
                'countDirection': 'down',
                'initialPaused': instance.is_paused or not instance.started,
                'roundId': instance.id
            })

    elif timer_type == 'totaltime':
        if hasattr(instance, 'time_spent'):  # Instance is a team_member
            # Get the time spent in seconds
            initial_seconds = instance.time_spent.total_seconds()

            config.update({
                'startValue': initial_seconds,
                'countDirection': 'up',
                'initialPaused': not instance.ontrack or instance.team.round.is_paused,
                'roundId': instance.team.round.id,
                'driverId': instance.id
            })

    elif timer_type == 'sessiontime':
        if hasattr(instance, 'current_session'):  # Instance is a team_member
            # Get the current session time in seconds
            if instance.current_session:
                initial_seconds = instance.current_session.total_seconds()
            else:
                initial_seconds = 0

            config.update({
                'startValue': initial_seconds,
                'countDirection': 'up',
                'initialPaused': not instance.ontrack or instance.team.round.is_paused,
                'roundId': instance.team.round.id,
                'driverId': instance.id
            })

    # Add any additional configurations
    if initial_value:
        config['startValue'] = initial_value

    # Create the HTML with data attributes for dynamic initialization
    html = f'<span id="{element_id}" class="timer" data-timer="true" data-config=\'{json.dumps(config)}\'>00:00:00</span>'

    return mark_safe(html)
