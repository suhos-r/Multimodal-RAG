"""Image + audio/video parsers. Heavy models optional; always return a searchable surrogate."""
from pathlib import Path

from .normalize import RawBlock


def parse_image(path: Path) -> list[RawBlock]:
    caption = ""
    ocr = ""
    try:
        from PIL import Image
        import pytesseract
        try:
            ocr = pytesseract.image_to_string(Image.open(path)).strip()[:2000]
        except Exception:
            ocr = ""
    except ImportError:
        pass
    # BLIP caption only if transformers+torch present (skip otherwise — keep local-first light)
    text = f"IMAGE {path.name}: {caption} OCR:{ocr}".strip()
    return [RawBlock(modality="image", text=text or f"IMAGE {path.name}", page=1, image_ref=path.name)]


def parse_media(path: Path) -> list[RawBlock]:
    suffix = path.suffix.lower()
    if suffix in (".mp3", ".wav", ".m4a", ".ogg"):
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(str(path))
            blocks = [RawBlock(modality="audio", text=s.text.strip(), page=i, ts=[s.start, s.end])
                      for i, s in enumerate(segments, start=1) if s.text.strip()]
            return blocks or [RawBlock(modality="audio", text="(empty transcript)", page=1)]
        except ImportError:
            return [RawBlock(modality="audio", text=f"(audio stored, whisper not installed: {path.name})", page=1)]
        except Exception as e:
            return [RawBlock(modality="audio", text=f"(transcribe failed: {e.__class__.__name__})", page=1)]
    # video: note + optional keyframe count via ffmpeg probe (no heavy caption by default)
    return [RawBlock(modality="video", text=f"(video stored: {path.name}; transcription runs in full worker)", page=1)]
