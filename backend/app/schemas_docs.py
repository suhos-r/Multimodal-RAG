import uuid
from pydantic import BaseModel


class DocumentOut(BaseModel):
    doc_id: uuid.UUID
    filename: str
    mime: str
    scope: str
    status: str
    page_count: int | None = None
    error: str | None = None
