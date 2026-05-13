from __future__ import annotations

from pydantic import BaseModel, Field


class VisualMetadataResult(BaseModel):
    visible_text: list[str] = Field(default_factory=list)
    probable_title: str = ""
    probable_date: str = ""
    disc_brand: str = ""
    disc_type: str = "unknown"
    handwritten: bool | None = None
    marker_color: str = ""
    physical_description: str = ""
    confidence: str = "low"
    needs_human_review: bool = True
