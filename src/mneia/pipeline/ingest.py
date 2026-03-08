from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from mneia.config import ConnectorConfig, MneiaConfig
from mneia.core.connector import BaseConnector
from mneia.memory.embeddings import EmbeddingClient
from mneia.memory.store import MemoryStore
from mneia.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    documents_ingested: int
    documents_skipped: int
    errors: list[str]
    checkpoint: str | None


async def ingest_connector(
    connector: BaseConnector,
    conn_config: ConnectorConfig,
    config: MneiaConfig,
    vector_store: VectorStore | None = None,
    embedding_client: EmbeddingClient | None = None,
) -> IngestResult:
    store = MemoryStore()
    name = connector.manifest.name

    authenticated = await connector.authenticate(conn_config.settings)
    if not authenticated:
        return IngestResult(
            documents_ingested=0,
            documents_skipped=0,
            errors=[f"Authentication failed for {name}"],
            checkpoint=conn_config.last_checkpoint,
        )

    since: datetime | None = None
    checkpoint_str = await store.get_checkpoint(name)
    if checkpoint_str:
        since = datetime.fromisoformat(checkpoint_str)

    ingested = 0
    skipped = 0
    errors: list[str] = []
    latest_timestamp: str | None = checkpoint_str

    async for doc in connector.fetch_since(since):
        try:
            doc_id = await store.store_document(doc)
            ingested += 1
            doc_ts = doc.timestamp.isoformat()
            if latest_timestamp is None or doc_ts > latest_timestamp:
                latest_timestamp = doc_ts

            if vector_store and vector_store.available and embedding_client and doc_id:
                try:
                    emb = await embedding_client.embed_document(
                        doc.title, doc.content, doc.source
                    )
                    if emb:
                        await vector_store.add_document(
                            doc_id=str(doc_id),
                            embedding=emb,
                            text=f"{doc.title}\n{doc.content[:2000]}",
                            metadata={
                                "source": doc.source,
                                "title": doc.title,
                                "content_type": doc.content_type,
                            },
                        )
                except Exception as e:
                    logger.debug(f"Embedding failed for {doc.source_id}: {e}")

        except Exception as e:
            errors.append(f"Failed to store {doc.source_id}: {e}")
            skipped += 1

    if latest_timestamp and latest_timestamp != checkpoint_str:
        await store.set_checkpoint(name, latest_timestamp)

    logger.info(f"Ingested {ingested} docs from {name} ({skipped} skipped, {len(errors)} errors)")
    return IngestResult(
        documents_ingested=ingested,
        documents_skipped=skipped,
        errors=errors,
        checkpoint=latest_timestamp,
    )
