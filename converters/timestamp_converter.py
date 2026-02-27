"""Timestamp conversion logic."""
from datetime import datetime, timezone

from dateutil import parser as dateparser


def parse_timestamp(input_str: str) -> dict:
    """Parse various timestamp formats and return all representations."""
    input_str = input_str.strip()
    dt = None

    # Try Unix timestamp (seconds)
    try:
        ts = float(input_str)
        if ts > 1e12:  # milliseconds
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        else:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        pass

    # Try ISO / natural date string
    if dt is None:
        try:
            dt = dateparser.parse(input_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except (ValueError, OverflowError):
            raise ValueError(f"Could not parse timestamp: {input_str}")

    if dt is None:
        raise ValueError(f"Could not parse timestamp: {input_str}")

    utc = dt.astimezone(timezone.utc)
    return {
        "unix": int(utc.timestamp()),
        "unix_ms": int(utc.timestamp() * 1000),
        "iso": utc.isoformat(),
        "utc": utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "human": utc.strftime("%B %d, %Y at %I:%M:%S %p UTC"),
        "date": utc.strftime("%Y-%m-%d"),
        "time": utc.strftime("%H:%M:%S"),
    }
