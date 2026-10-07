"""Persistent memory: PostgreSQL is the source of truth, ChromaDB provides semantic recall."""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.db import Memory

log = logging.getLogger(__name__)
EMBED_CHARS = 1200  # embedding models only "see" the start of long text, so embed title + opening


class MemoryStore:
    def __init__(self, session_factory, chroma_host: str, chroma_port: int, collection: str = "orchestrai_memory"):
        self.session_factory = session_factory
        self.chroma_host, self.chroma_port, self.collection_name = chroma_host, chroma_port, collection
        self._collection = None

    def _chroma(self):
        if self._collection is None:
            import chromadb

            client = chromadb.HttpClient(host=self.chroma_host, port=self.chroma_port)
            self._collection = client.get_or_create_collection(self.collection_name)
        return self._collection

    def save(self, title: str, content: str, category: str = "General", source: str = "agent") -> int:
        with self.session_factory() as session:
            memory = Memory(title=title[:200], content=content, category=category[:64], source=source[:64])
            session.add(memory)
            session.commit()
            memory_id = memory.id
        try:
            self._chroma().add(
                ids=[str(memory_id)],
                documents=[f"{title}\n{content[:EMBED_CHARS]}"],
                metadatas=[{"title": title[:200], "category": category[:64], "source": source[:64]}],
            )
        except Exception:  # noqa: BLE001 - the row is saved; semantic recall is best-effort
            log.exception("could not index memory %s in ChromaDB", memory_id)
        return memory_id

    def search(self, query: str, k: int = 4) -> list[dict]:
        result = self._chroma().query(query_texts=[query], n_results=k)
        rows = zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0], strict=False
        )
        return [
            {
                "id": int(memory_id),
                "title": meta.get("title", ""),
                "category": meta.get("category", ""),
                "snippet": document[:600],
                "distance": round(float(distance), 4),
            }
            for memory_id, document, meta, distance in rows
        ]

    def recent(self, limit: int = 20) -> list[dict]:
        with self.session_factory() as session:
            rows = session.execute(select(Memory).order_by(Memory.id.desc()).limit(limit)).scalars().all()
        return [
            {
                "id": m.id,
                "title": m.title,
                "category": m.category,
                "source": m.source,
                "snippet": m.content[:300],
                "created_at": m.created_at.isoformat(),
            }
            for m in rows
        ]
