from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from app.core.placeholders import expand_date_placeholder
from app.core.schema import ProviderNeutralQuery


@dataclass
class ProviderResult:
    provider: str
    query_used: str
    urls: Sequence[str]
    meta: dict


def build_query_from_schema(schema: ProviderNeutralQuery) -> str:
    # Keywords
    if schema.boolean == "OR":
        core = " OR ".join(schema.keywords)
    else:
        core = " ".join(schema.keywords)

    parts: list[str] = [core]

    # Sites
    if schema.filters.sites:
        parts.extend([f"site:{s}" for s in schema.filters.sites])

    # Dates (after/before); expand placeholders to ISO if present
    if schema.filters.date_after:
        try:
            da = expand_date_placeholder(schema.filters.date_after)
            parts.append(f"after:{da}")
        except Exception:
            # if placeholder unsupported we skip adding; upstream phases should validate
            pass
    if schema.filters.date_before:
        try:
            db = expand_date_placeholder(schema.filters.date_before)
            parts.append(f"before:{db}")
        except Exception:
            pass

    return " ".join([p for p in parts if p])


class SearchProviderAdapter(Protocol):
    name: str

    async def search(self, schema: ProviderNeutralQuery, options: dict | None = None) -> ProviderResult:
        ...
