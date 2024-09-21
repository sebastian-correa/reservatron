"""Various time utilities."""

from datetime import datetime
from zoneinfo import ZoneInfo


def is_aware(dt: datetime) -> bool:
    """Check if a datetime is aware.

    See https://docs.python.org/3/library/datetime.html#determining-if-an-object-is-aware-or-naive.

    Args:
        dt (datetime): The datetime to check.

    Returns:
        bool: True if the datetime is aware, False otherwise.
    """
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(None) is not None


def localize(dt: datetime, to_timezone: ZoneInfo) -> datetime:
    """Localize a datetime to the channel's timezone.

    Args:
        dt (datetime): The datetime to localize. If naive, attaches the channel's timezone. If
            aware, converts to the channel's timezone.
        to_timezone (ZoneInfo): The timezone to localize to.

    Returns:
        datetime: The localized datetime.
    """
    if is_aware(dt):
        return dt.astimezone(to_timezone)
    return dt.replace(tzinfo=to_timezone)
