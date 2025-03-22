from django import template

register = template.Library()

@register.filter
def duration_difference_seconds(round):
    if round:
        return (round.duration - round.time_elapsed).total_seconds()
    return 0

@register.filter
def round_is_paused(round):
    if round:
        return "true" if round.is_paused else "false"
    return "true"
