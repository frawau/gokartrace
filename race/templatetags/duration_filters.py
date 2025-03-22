from django import template

register = template.Library()

@register.filter
def duration_difference_seconds(duration, round):
    if duration and round:
        return (duration - round.time_elapsed).total_seconds()
    return 0
