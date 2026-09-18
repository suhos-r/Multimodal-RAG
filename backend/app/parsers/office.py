"""Lightweight text/office parsers. Heavy deps are optional; fall back to plain-text."""
from pathlib import Path

from .normalize import RawBlock


def parse_text_file(path: Path) -> list[RawBlock]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [RawBlock(modality="text", text=text.strip() or "(empty file)", page=1)]


def parse_csv(path: Path) -> list[RawBlock]:
    import csv
    rows = []
    with open(path, newline="", encoding="utf-8", errors="ignore") as f:
        for i, row in enumerate(csv.DictReader(f) or []):
            rows.append(f"Row {i}: " + ", ".join(f"{k}={v}" for k, v in row.items()))
            if len(rows) > 500:
                break
    return [RawBlock(modality="table", text="\n".join(rows) or "(empty csv)", page=1)]


def parse_office(path: Path, mime: str) -> list[RawBlock]:
    suffix = path.suffix.lower()
    try:
        if suffix == ".docx":
            from docx import Document as Docx
            doc = Docx(str(path))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            return [RawBlock(modality="text", text=text or "(empty docx)", page=1)]
        if suffix == ".pptx":
            from pptx import Presentation
            prs = Presentation(str(path))
            blocks = []
            for i, slide in enumerate(prs.slides, start=1):
                t = "\n".join(s.text for s in slide.shapes if hasattr(s, "text") and s.text.strip())
                if t.strip():
                    blocks.append(RawBlock(modality="text", text=t, page=i))
            return blocks or [RawBlock(modality="text", text="(empty pptx)", page=1)]
        if suffix in (".xlsx", ".xls"):
            import openpyxl
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
            blocks = []
            for ws in wb.worksheets:
                lines = []
                for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
                    vals = [str(c) for c in row if c not in (None, "")]
                    if vals:
                        lines.append(f"Row {r}: " + " | ".join(vals))
                    if len(lines) > 300:
                        break
                if lines:
                    blocks.append(RawBlock(modality="table", text=f"Sheet {ws.title}\n" + "\n".join(lines), page=1))
            return blocks or [RawBlock(modality="text", text="(empty workbook)", page=1)]
    except ImportError as e:
        return [RawBlock(modality="text", text=f"(parser missing dep {e.name}; stored raw path {path.name})", page=1)]
    # md/html/txt fallback
    return parse_text_file(path)
