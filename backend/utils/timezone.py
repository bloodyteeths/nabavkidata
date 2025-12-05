"""
Timezone utilities for Nabavkidata
All dates/times should be in Macedonia/Skopje timezone (Europe/Skopje)
"""
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

# Macedonia timezone
MACEDONIA_TZ = ZoneInfo("Europe/Skopje")


def now_mk() -> datetime:
    """
    Get current datetime in Macedonia timezone

    Returns:
        datetime: Current time in Europe/Skopje timezone
    """
    return datetime.now(MACEDONIA_TZ)


def today_mk() -> date:
    """
    Get current date in Macedonia timezone

    Returns:
        date: Current date in Europe/Skopje timezone
    """
    return now_mk().date()


def format_mk_datetime(dt: datetime = None) -> str:
    """
    Format datetime for display in Macedonian format

    Args:
        dt: datetime to format (defaults to now)

    Returns:
        str: Formatted date string like "05.12.2025 14:30"
    """
    if dt is None:
        dt = now_mk()
    return dt.strftime('%d.%m.%Y %H:%M')


def format_mk_date(d: date = None) -> str:
    """
    Format date for display in Macedonian format

    Args:
        d: date to format (defaults to today)

    Returns:
        str: Formatted date string like "05.12.2025"
    """
    if d is None:
        d = today_mk()
    return d.strftime('%d.%m.%Y')


def get_mk_weekday_name(dt: datetime = None) -> str:
    """
    Get Macedonian name for day of week

    Args:
        dt: datetime (defaults to now)

    Returns:
        str: Macedonian day name
    """
    if dt is None:
        dt = now_mk()

    weekdays = {
        0: "Понеделник",
        1: "Вторник",
        2: "Среда",
        3: "Четврток",
        4: "Петок",
        5: "Сабота",
        6: "Недела"
    }
    return weekdays[dt.weekday()]


def get_ai_date_context() -> str:
    """
    Get formatted date/time context string for AI prompts

    Returns:
        str: Formatted context string in Macedonian
    """
    now = now_mk()
    weekday = get_mk_weekday_name(now)

    return f"""ТЕКОВЕН ДАТУМ И ВРЕМЕ: {now.strftime('%d.%m.%Y %H:%M')} ({weekday})
Временска зона: Македонија (Europe/Skopje)

Ова е важно за:
- Определување дали тендер е сè уште отворен (ако краен рок < денес = затворен)
- Колку време остава до краен рок
- Временски релевантни прашања"""


def is_tender_open(closing_date: date) -> bool:
    """
    Check if a tender is still open based on closing date

    Args:
        closing_date: The tender's closing date

    Returns:
        bool: True if tender is still open (closing_date >= today)
    """
    if closing_date is None:
        return True  # Unknown closing date, assume open
    return closing_date >= today_mk()


def days_until_closing(closing_date: date) -> int:
    """
    Calculate days remaining until tender closes

    Args:
        closing_date: The tender's closing date

    Returns:
        int: Days remaining (negative if past)
    """
    if closing_date is None:
        return None
    return (closing_date - today_mk()).days


def to_mk_timezone(dt: datetime) -> datetime:
    """
    Convert a datetime to Macedonia timezone

    Args:
        dt: datetime to convert (can be naive or aware)

    Returns:
        datetime: Datetime in Macedonia timezone
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        # Assume UTC for naive datetimes
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    return dt.astimezone(MACEDONIA_TZ)
