from django import template

register = template.Library()

@register.filter
def duration_difference_seconds(duration, time_elapsed):
    if duration and time_elapsed:
        return (duration - time_elapsed).total_seconds()
    return 0
