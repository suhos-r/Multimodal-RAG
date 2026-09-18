"""Qdrant wrapper (self-hosted, free). Unavailable -> False, callers use Postgres lexical path."""
import uuid

from ..config import settings

COLLECTION = "text-v1"


class QdrantStore:
    def __init__(self):
        self.available = False
        self._client = None
        try:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None, timeout=5)
            self._client.get_collections()
            self.available = True
        except Exception:
            self._client = None

    def ensure(self, dim: int) -> bool:
        if not self.available:
            return False
        try:
            from qdrant_client.http import models
            try:
                col = self._client.get_collection(COLLECTION)
                if col.config.params.vectors.size != dim:
                    self._client.recreate_collection(
                        COLLECTION, vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE))
            except Exception:
                self._client.create_collection(
                    COLLECTION, vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE))
            try:
                self._client.create_payload_index(COLLECTION, field_name="scope",
                                                  field_schema=models.PayloadSchemaType.KEYWORD)
            except Exception:
                pass
            return True
        except Exception:
            self.available = False
            return False

    def upsert(self, points: list[dict]) -> bool:
        """points: [{vector, payload{scope,doc_id,chunk_id,page,modality,text}}]"""
        if not self.available or not points:
            return False
        try:
            from qdrant_client.http.models import PointStruct
            self._client.upsert(COLLECTION, points=[
                PointStruct(id=str(uuid.uuid4()), vector=p["vector"], payload=p["payload"]) for p in points])
            return True
        except Exception:
            return False

    def search(self, vector: list[float], scopes: list[str], doc_ids: list[str] | None = None,
               limit: int = 20) -> list[dict]:
        if not self.available:
            return []
        try:
            from qdrant_client.http import models
            must = [models.FieldCondition(key="scope", match=models.MatchAny(any=scopes))]
            if doc_ids:
                must.append(models.FieldCondition(key="doc_id", match=models.MatchAny(any=doc_ids)))
            res = self._client.search(COLLECTION, query_vector=vector,
                                      query_filter=models.Filter(must=must), limit=limit,
                                      with_payload=True)
            return [{"chunk_id": (r.payload or {}).get("chunk_id"), "score": r.score,
                     "payload": r.payload or {}} for r in res]
        except Exception:
            return []

    def delete_doc(self, doc_id: str) -> None:
        if not self.available:
            return
        try:
            from qdrant_client.http import models
            self._client.delete(COLLECTION, points_selector=models.FilterSelector(filter=models.Filter(
                must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))])))
        except Exception:
            pass
