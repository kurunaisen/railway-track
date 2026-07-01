"""Единый тип строки таблицы обхода."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AssetKind = Literal["track", "switch"]


class RailwayRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    location: str | None = None
    asset_kind: AssetKind | None = Field(default=None, alias="assetKind")
    asset_number: str | None = Field(default=None, alias="assetNumber")
    reference: str | None = None
    defect: str | None = None
    speed_limit: int | None = Field(default=None, alias="speedLimit")
    note: str | None = None
    source_text: str = Field(alias="sourceText")
    warnings: list[str] = Field(default_factory=list)

    def to_api_dict(self) -> dict:
        return self.model_dump(by_alias=True)
