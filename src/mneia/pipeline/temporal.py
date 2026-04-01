from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone


def parse_temporal_expression(
    text: str,
    reference: datetime | None = None,
) -> tuple[datetime, datetime] | None:
    """Parse a relative or absolute temporal expression into a (start, end) range.

    Supported patterns:
    - today / yesterday / tomorrow
    - this / last / next week
    - this / last / next month
    - this / last year
    - last N days / weeks / months
    - Q1–Q4 with optional year (e.g. "Q2 2024")
    - last <weekday> (e.g. "last Monday")
    - month name with optional year (e.g. "in March", "January 2024")

    Returns:
        (start, end) tuple of UTC-aware datetimes, or None if no match.
    """
    if reference is None:
        reference = datetime.now(timezone.utc)

    t = text.lower().strip()
    today = reference.replace(hour=0, minute=0, second=0, microsecond=0)

    def _end(d: datetime) -> datetime:
        return d.replace(hour=23, minute=59, second=59, microsecond=999999)

    # today / yesterday / tomorrow
    if re.search(r"\btoday\b", t):
        return today, _end(today)
    if re.search(r"\byesterday\b", t):
        y = today - timedelta(days=1)
        return y, _end(y)
    if re.search(r"\btomorrow\b", t):
        y = today + timedelta(days=1)
        return y, _end(y)

    # week
    if re.search(r"\bthis\s+week\b", t):
        mon = today - timedelta(days=today.weekday())
        return mon, _end(mon + timedelta(days=6))
    if re.search(r"\blast\s+week\b", t):
        mon = today - timedelta(days=today.weekday() + 7)
        return mon, _end(mon + timedelta(days=6))
    if re.search(r"\bnext\s+week\b", t):
        mon = today - timedelta(days=today.weekday() - 7)
        return mon, _end(mon + timedelta(days=6))

    # month
    if re.search(r"\bthis\s+month\b", t):
        start = today.replace(day=1)
        nxt = (start + timedelta(days=32)).replace(day=1)
        return start, nxt - timedelta(seconds=1)
    if re.search(r"\blast\s+month\b", t):
        first = today.replace(day=1)
        end_of_lm = first - timedelta(days=1)
        return end_of_lm.replace(day=1), _end(end_of_lm)
    if re.search(r"\bnext\s+month\b", t):
        first = today.replace(day=1)
        start = (first + timedelta(days=32)).replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
        return start, end

    # year
    if re.search(r"\bthis\s+year\b", t):
        return today.replace(month=1, day=1), _end(today.replace(month=12, day=31))
    if re.search(r"\blast\s+year\b", t):
        y = today.year - 1
        return today.replace(year=y, month=1, day=1, hour=0, minute=0, second=0, microsecond=0), \
               today.replace(year=y, month=12, day=31, hour=23, minute=59, second=59, microsecond=0)

    # last N days/weeks/months
    m = re.search(r"\blast\s+(\d+)\s+(day|week|month)s?\b", t)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = timedelta(days=n) if unit == "day" else (
            timedelta(weeks=n) if unit == "week" else timedelta(days=n * 30)
        )
        return today - delta, _end(today)

    # Q1–Q4 with optional year
    m = re.search(r"\bq([1-4])\s*(\d{4})?\b", t)
    if m:
        q = int(m.group(1))
        year = int(m.group(2)) if m.group(2) else today.year
        q_start = (q - 1) * 3 + 1
        q_end = q * 3
        start = today.replace(year=year, month=q_start, day=1, hour=0, minute=0, second=0, microsecond=0)
        if q_end < 12:
            end = today.replace(year=year, month=q_end + 1, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)
        else:
            end = _end(today.replace(year=year, month=12, day=31))
        return start, end

    # last <weekday>
    dow_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }
    m = re.search(
        r"\blast\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", t,
    )
    if m:
        target = dow_map[m.group(1)]
        days_back = (today.weekday() - target) % 7 or 7
        d = today - timedelta(days=days_back)
        return d, _end(d)

    # month name with optional year
    month_map = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    m = re.search(
        r"\b(?:in\s+)?(january|february|march|april|may|june|july|august|"
        r"september|october|november|december)\s*(\d{4})?\b",
        t,
    )
    if m:
        mon = month_map[m.group(1)]
        year = int(m.group(2)) if m.group(2) else today.year
        if year == today.year and mon > today.month:
            year -= 1
        start = today.replace(year=year, month=mon, day=1, hour=0, minute=0, second=0, microsecond=0)
        if mon == 12:
            end_d = today.replace(year=year, month=12, day=31)
        else:
            end_d = today.replace(year=year, month=mon + 1, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        return start, _end(end_d)

    return None


def extract_temporal_range(
    question: str,
    reference: datetime | None = None,
) -> tuple[datetime, datetime] | None:
    """Extract the first temporal range from a question string."""
    return parse_temporal_expression(question, reference)
