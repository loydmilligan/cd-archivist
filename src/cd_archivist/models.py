from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class DiscStatus(StrEnum):
    CAPTURED = "captured"
    RIPPED = "ripped"
    PAIRED = "paired"
    METADATA_GENERATED = "metadata_generated"
    NEEDS_REVIEW = "needs_review"
    ACCEPTED = "accepted"
    PUBLISHED = "published"
    ERROR = "error"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CaptureSession(BaseModel):
    capture_id: str
    started_at: datetime
    ended_at: datetime | None = None
    trigger: str = "unknown"
    camera_device: str = "unknown"
    image_paths: list[Path] = Field(default_factory=list)
    notes: str = ""


class RipSession(BaseModel):
    rip_id: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    source_machine: str = "g4"
    source_path: Path | None = None
    audio_paths: list[Path] = Field(default_factory=list)
    track_count: int | None = None
    format: str | None = None
    rip_log_path: Path | None = None
    status: str = "unknown"


class DiscMetadata(BaseModel):
    visible_text: list[str] = Field(default_factory=list)
    probable_title: str = ""
    probable_date: str = ""
    disc_brand: str = ""
    disc_type: str = "unknown"
    handwritten: bool | None = None
    marker_color: str = ""
    physical_description: str = ""
    confidence: Confidence = Confidence.LOW
    needs_human_review: bool = True


class PairingRecord(BaseModel):
    capture_id: str
    rip_id: str
    paired_at: datetime
    method: Literal["timestamp", "manual", "g4_event", "unknown"] = "unknown"
    confidence: Confidence = Confidence.LOW
    notes: str = ""


class ErrorRecord(BaseModel):
    occurred_at: datetime
    component: str
    message: str
    details: dict = Field(default_factory=dict)


class DiscManifest(BaseModel):
    schema_version: str = "0.1"
    disc_id: str
    created_at: datetime
    updated_at: datetime
    status: DiscStatus = DiscStatus.NEEDS_REVIEW
    captures: list[CaptureSession] = Field(default_factory=list)
    rips: list[RipSession] = Field(default_factory=list)
    pairings: list[PairingRecord] = Field(default_factory=list)
    metadata: DiscMetadata = Field(default_factory=DiscMetadata)
    errors: list[ErrorRecord] = Field(default_factory=list)
