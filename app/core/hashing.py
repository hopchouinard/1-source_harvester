from __future__ import annotations

import hashlib


def url_hash(url: str) -> str:  # Phase H
    return hashlib.sha1(url.encode("utf-8")).hexdigest()

