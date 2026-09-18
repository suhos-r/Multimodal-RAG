"""Dispatch mime/suffix -> parser. Never raises; returns (blocks, warning)."""
from pathlib import Path

from .normalize import RawBlock
from .office import parse_csv, parse_office, parse_text_file
from .pdf import parse_pdf
from .media import parse_image, parse_media


def parse_file(blob_path: str, mime: str) -> tuple[list[RawBlock], str | None]:
    path = Path(blob_path)
    suffix = path.suffix.lower()
    warning = None
    try:
        if mime == "application/pdf" or suffix == ".pdf":
            return parse_pdf(path), None
        if suffix in (".png", ".jpg", ".jpeg", ".webp"):
            return parse_image(path), None
        if suffix in (".mp3", ".wav", ".m4a", ".ogg", ".mp4", ".mov"):
            return parse_media(path), None
        if suffix == ".csv":
            return parse_csv(path), None
        if suffix in (".docx", ".pptx", ".xlsx", ".xls", ".md", ".html", ".txt"):
            return parse_office(path, mime), None
        # unknown -> try plain text
        return parse_text_file(path), f"unknown type {suffix}, treated as text"
    except Exception as e:
        return [RawBlock(modality="text", text=f"(parse failed: {e.__class__.__name__})", page=1)], str(e)[:300]
