from __future__ import annotations

import re
from datetime import datetime


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATE_PH_RE = re.compile(r"^\{\{(today|yesterday|days_ago:(\d+))\}\}$")


def is_iso_date(s: str) -> bool:
    if not _ISO_DATE_RE.match(s):
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def is_allowed_placeholder(s: str) -> bool:
    return _DATE_PH_RE.match(s) is not None


def is_valid_date_or_placeholder(s: str) -> bool:
    return is_iso_date(s) or is_allowed_placeholder(s)

