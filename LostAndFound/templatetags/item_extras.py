"""Small, read-only helpers used by the redesigned templates."""
from django import template

register = template.Library()


@register.filter
def count_status(items, status):
    """Count how many items in an iterable have the given status.

    Used for the status summaries on the dashboard and boards, e.g.
    ``{{ my_lost_reports|count_status:"Open" }}``. Works on querysets and
    lists that the view has already evaluated, so it adds no queries when the
    sequence is already cached.
    """
    try:
        return sum(1 for item in items if getattr(item, 'status', None) == status)
    except TypeError:
        return 0


@register.filter
def short_since(value):
    """Largest unit only, e.g. '6 hours ago' instead of '6 hours, 53 minutes'."""
    from django.utils.timesince import timesince
    if not value:
        return ''
    return timesince(value).split(',')[0].replace('\xa0', ' ') + ' ago'
