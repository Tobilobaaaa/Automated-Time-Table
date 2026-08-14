from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    """Safe dict lookup for nested timetable grid access."""
    if mapping is None:
        return None
    try:
        return mapping.get(key)
    except AttributeError:
        return None
