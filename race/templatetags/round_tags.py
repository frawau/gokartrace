# yourapp/templatetags/round_tags.py
from django import template

register = template.Library()


@register.simple_tag
def check_driver_transgression(member):
    """
    Check if a team member has a transgression.
    Returns True or False.
    """
    return member.has_transgression


@register.simple_tag
def check_team_transgression(round_team):
    """
    Check if a team has a transgression.

    """
    return round_team.has_transgression
