from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator
from pydantic.config import ConfigDict

from app.core.validation import is_valid_date_or_placeholder


BooleanOp = Literal["AND", "OR"]


class Filters(BaseModel):
    sites: list[str] = Field(default_factory=list)
    date_after: str | None = None
    date_before: str | None = None
    lang: str | None = None
    geo: str | None = None
    max_results: int = 50

    model_config = ConfigDict(extra="forbid")

    @field_validator("sites")
    @classmethod
    def validate_sites(cls, v: list[str]) -> list[str]:
        # Enforce limit of 20 sites (Phase K mentions; adopt early here)
        if len(v) > 20:
            raise ValueError("sites cannot exceed 20 entries")
        return v

    @field_validator("max_results")
    @classmethod
    def validate_max_results(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_results must be > 0")
        if v > 100:
            raise ValueError("max_results must be <= 100")
        return v

    @field_validator("date_after", "date_before")
    @classmethod
    def validate_dates(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not is_valid_date_or_placeholder(v):
            raise ValueError("date must be ISO YYYY-MM-DD or allowed placeholder")
        return v


class ProviderNeutralQuery(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    boolean: BooleanOp = "AND"
    filters: Filters = Field(default_factory=Filters)

    model_config = ConfigDict(extra="forbid")

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("keywords must be a non-empty list")
        if len(v) > 12:
            raise ValueError("keywords cannot exceed 12 entries")
        return v

