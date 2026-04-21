from django import template

register = template.Library()

@register.filter
def vnd(x):
    try:
        x = int(x)
        return f"{x:,}".replace(",", ".")
    except Exception:
        return x


@register.filter
def vnd_comma(x):
    try:
        return f"{int(x):,}"
    except Exception:
        return x
