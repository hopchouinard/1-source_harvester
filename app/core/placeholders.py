from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional

_DATE_PH_RE = re.compile(r"^\{\{(today|yesterday|days_ago:(\d+))\}\}$")


def _resolve_date_token(token: str, today: Optional[date] = None) -> str:
    """Resolve a single date placeholder token to ISO date (YYYY-MM-DD).

    Supported tokens:
      - {{today}}
      - {{yesterday}}
      - {{days_ago:N}}  (N >= 0)
    """
    m = _DATE_PH_RE.match(token)
    if not m:
        raise ValueError(f"Unknown or invalid placeholder: {token}")
    name = m.group(1)
    n_str = m.group(2)

    base = today or date.today()
    if name == "today":
        d = base
    elif name == "yesterday":
        d = base - timedelta(days=1)
    else:  # days_ago:N
        n = int(n_str or "0")
        d = base - timedelta(days=n)
    return d.isoformat()


def expand_date_placeholder(value: str, today: Optional[date] = None) -> str:
    """Expand a date value if it is a placeholder; otherwise return unchanged.

    Raises ValueError for unknown placeholder formats.
    """
    if _DATE_PH_RE.match(value):
        return _resolve_date_token(value, today=today)
    # If it looks like a placeholder but is not allowed, raise
    if value.startswith("{{") and value.endswith("}}"):
        raise ValueError(f"Unknown or invalid placeholder: {value}")
    return value
