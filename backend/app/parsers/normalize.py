"""Canonical block: single unit from any parser before chunking."""
from pydantic import BaseModel


class RawBlock(BaseModel):
    modality: str = "text"  # text | table | image | audio | video
    text: str
    page: int | None = None
    bbox: dict | None = None
    ts: list | None = None
    image_ref: str | None = None


class CanonicalBlock(RawBlock):
    pass
