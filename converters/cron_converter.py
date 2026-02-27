"""Cron expression parsing logic."""
from datetime import datetime

from croniter import croniter


_MONTHS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def cron_parse(cron_expr: str) -> dict:
    """Parse a cron expression and return a human-readable description + next runs."""
    cron_expr = cron_expr.strip()
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError("Cron expression must have exactly 5 fields (minute hour day month weekday)")

    description = _describe(parts)
    base = datetime.now()
    cron = croniter(cron_expr, base)
    next_runs = [cron.get_next(datetime).strftime("%Y-%m-%d %H:%M:%S") for _ in range(5)]

    return {"expression": cron_expr, "description": description, "next_runs": next_runs}


def _describe(parts: list[str]) -> str:
    minute, hour, dom, month, dow = parts

    pieces = []

    # Time
    if minute == "*" and hour == "*":
        pieces.append("Every minute")
    elif minute == "*":
        pieces.append(f"Every minute past hour {hour}")
    elif hour == "*":
        pieces.append(f"At minute {minute} of every hour")
    else:
        pieces.append(f"At {hour.zfill(2)}:{minute.zfill(2)}")

    # Day of month
    if dom != "*":
        pieces.append(f"on day {dom} of the month")

    # Month
    if month != "*":
        try:
            idx = int(month)
            pieces.append(f"in {_MONTHS[idx]}")
        except (ValueError, IndexError):
            pieces.append(f"in month {month}")

    # Day of week
    if dow != "*":
        try:
            idx = int(dow) % 7
            pieces.append(f"on {_DAYS[idx]}")
        except (ValueError, IndexError):
            pieces.append(f"on weekday {dow}")

    return ", ".join(pieces)
