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


@register.filter
def mmss_format(timedelta_obj):
    """Format timedelta as MM:SS for form inputs"""
    if not timedelta_obj:
        return "00:00"
    
    total_seconds = int(timedelta_obj.total_seconds())
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"
