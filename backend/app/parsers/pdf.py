"""PDF parser: PyMuPDF preferred, pypdf fallback, OCR note if empty."""
from pathlib import Path

from .normalize import RawBlock


def parse_pdf(path: Path) -> list[RawBlock]:
    # Try PyMuPDF
    try:
        import fitz
        doc = fitz.open(str(path))
        blocks: list[RawBlock] = []
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if len(text) < 50:
                text += "\n[OCR may be needed: page has little extractable text]"
            if text.strip():
                blocks.append(RawBlock(modality="text", text=text, page=i))
        return blocks or [RawBlock(modality="text", text="(empty pdf)", page=1)]
    except ImportError:
        pass
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        blocks = []
        for i, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                blocks.append(RawBlock(modality="text", text=text, page=i))
        return blocks or [RawBlock(modality="text", text="(empty pdf)", page=1)]
    except ImportError:
        return [RawBlock(modality="text", text=f"(no pdf backend installed; stored {path.name})", page=1)]
