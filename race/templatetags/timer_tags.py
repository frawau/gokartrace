# raceinfo/templatetags/timer_tags.py
from django import template
from django.utils.safestring import mark_safe
import json
import datetime as dt # Make sure datetime is imported if needed for type hints or checks

register = template.Library()

@register.simple_tag
def timer_widget(element_id, timer_type, instance=None, initial_value=None, show_hours=True, show_minutes=True):
    """
    Renders a timer widget span element for initialization by timer-widget.js.

    Args:
        element_id (str): The base HTML element ID (e.g., "total-time-").
                          The instance ID will be appended for member timers.
        timer_type (str): One of 'countdownDisplay', 'totaltime', or 'sessiontime'.
        instance (Model Instance): The model instance (Round or team_member). Required for configuration.
        initial_value (float, optional): Override calculated startValue. Defaults to None.
        show_hours (bool): Whether to include hours in the display format. Defaults to True.
        show_minutes (bool): Whether to include minutes in the display format. Defaults to True.
    """
    # If no instance provided, we cannot configure the timer properly.
    # Return a placeholder or an error comment.
    if not instance:
        # Ensure element_id is safe if used directly
        safe_element_id = str(element_id).replace(" ", "_").replace(":", "-")
        return mark_safe(f'<span id="{safe_element_id}" class="timer text-muted">--:--:--</span> ')

    # Determine the final element ID based on instance type
    final_element_id = str(element_id) # Default for round timer
    if hasattr(instance, 'id') and timer_type in ['totaltime', 'sessiontime']:
         # Append instance ID for driver-specific timers
         final_element_id = f"{element_id}{instance.id}"
    elif timer_type == 'countdownDisplay' and hasattr(instance, 'id'):
        # For countdown, use the passed element_id directly (e.g., "race-countdown")
        final_element_id = str(element_id)


    # Default configuration
    config = {
        'elementId': final_element_id, # Use the final determined ID
        'showHours': bool(show_hours), # Ensure boolean
        'showMinutes': bool(show_minutes), # Ensure boolean
        'timerType': timer_type,
        'startValue': 0, # Default start value
        'countDirection': 'up', # Default direction
        'initialPaused': True, # Default to paused
        'roundId': None,
        'driverId': None,
    }

    try:
        if timer_type == 'countdownDisplay' and hasattr(instance, 'duration'): # Instance is a Round
            round_instance = instance
            initial_seconds = round_instance.duration.total_seconds()
            # Calculate remaining time accurately
            if round_instance.started and not round_instance.ended:
                 # Ensure time_elapsed calculation handles potential None values if needed
                 elapsed_seconds = round_instance.time_elapsed.total_seconds() if round_instance.time_elapsed else 0
                 remaining = initial_seconds - elapsed_seconds
            elif not round_instance.started:
                 remaining = initial_seconds # Not started, show full duration
            else: # Ended
                 remaining = 0 # Race finished

            config.update({
                'startValue': max(0, remaining), # Don't start negative
                'countDirection': 'down',
                # Pause if not started OR explicitly paused OR ended
                'initialPaused': not round_instance.started or round_instance.is_paused or round_instance.ended,
                'roundId': round_instance.id
            })

        elif timer_type == 'totaltime' and hasattr(instance, 'time_spent'): # Instance is a team_member
            member = instance
            # Ensure time_spent calculation returns timedelta
            time_spent_delta = member.time_spent if isinstance(member.time_spent, dt.timedelta) else dt.timedelta()
            initial_seconds = time_spent_delta.total_seconds()
            round_instance = member.team.round # Get the related round

            config.update({
                'startValue': initial_seconds,
                'countDirection': 'up',
                # Pause if driver not on track OR round not started OR round paused OR round ended
                'initialPaused': not member.ontrack or not round_instance.started or round_instance.is_paused or round_instance.ended,
                'roundId': round_instance.id,
                'driverId': member.id
            })

        elif timer_type == 'sessiontime' and hasattr(instance, 'ontrack'): # Instance is a team_member
            member = instance
            round_instance = member.team.round # Get the related round

            # Session timer always starts from 0 when activated by JS.
            # Set startValue to 0 here for consistency.
            initial_seconds = 0

            config.update({
                'startValue': initial_seconds,
                'countDirection': 'up',
                 # Pause if driver not on track OR round not started OR round paused OR round ended
                'initialPaused': not member.ontrack or not round_instance.started or round_instance.is_paused or round_instance.ended,
                'roundId': round_instance.id,
                'driverId': member.id
            })

        else:
             # Handle cases where instance type doesn't match timer_type expectation
             return mark_safe(f'<span id="{final_element_id}" class="timer text-danger">--:--:--</span> ')

    except Exception as e:
         # Catch potential errors during attribute access (e.g., related object doesn't exist)
         print(f"Error configuring timer widget {final_element_id}: {e}") # Log error server-side
         return mark_safe(f'<span id="{final_element_id}" class="timer text-danger">Error</span> ')


    # Allow overriding the calculated startValue if explicitly provided
    if initial_value is not None:
        try:
            config['startValue'] = float(initial_value)
        except (ValueError, TypeError):
            print(f"Warning: Invalid initial_value '{initial_value}' for timer {final_element_id}. Using calculated value.")


    # Serialize config safely for HTML attribute
    # Use json.dumps with separators to minimize output size slightly
    json_config = json.dumps(config, separators=(',', ':'))

    # Create the HTML span element for the timer widget
    # The initial text content will be replaced by timer-widget.js on initialization
    html = f'<span id="{final_element_id}" class="timer" data-timer="true" data-config=\'{json_config}\'>--:--:--</span>'

    return mark_safe(html)
