from __future__ import annotations

import logging
from typing import Any

from mneia.core.llm import LLMClient
from mneia.memory.embeddings import EmbeddingClient
from mneia.memory.graph import GraphEdge, GraphNode, KnowledgeGraph
from mneia.memory.store import Entity, MemoryStore, StoredDocument
from mneia.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = (
    "You extract structured entities from personal documents.\n"
    "Return JSON with exactly this schema:\n"
    '{"entities": [{"name": "...", '
    '"type": "person|project|topic|decision|belief|meeting|tool|organization", '
    '"description": "brief description"}], '
    '"relationships": [{"source": "entity name", "target": "entity name", '
    '"relation": "works_with|discussed_in|decided_on|related_to|part_of|'
    'uses|manages|reports_to|met_with"}]}\n'
    "Rules:\n"
    "- Only extract clearly stated facts. Do not infer or hallucinate.\n"
    "- Names should be proper nouns or specific identifiers.\n"
    "- Keep descriptions under 30 words.\n"
    "- Limit to the 10 most important entities per document.\n"
    "- Relationships must reference entities you extracted."
)


def _make_node_id(name: str, entity_type: str) -> str:
    slug = name.lower().replace(" ", "-").replace("'", "")
    return f"{entity_type}:{slug}"


async def extract_entities(
    doc: StoredDocument,
    llm: LLMClient,
) -> dict[str, Any]:
    content = doc.content[:3000]
    prompt = f"""Extract entities and relationships from this {doc.content_type}:

Title: {doc.title}
Source: {doc.source}
Content:
{content}"""

    try:
        result = await llm.generate_json(prompt, system=EXTRACTION_SYSTEM_PROMPT)
        entities = result.get("entities", [])
        relationships = result.get("relationships", [])
        if not isinstance(entities, list):
            entities = []
        if not isinstance(relationships, list):
            relationships = []
        return {"entities": entities, "relationships": relationships}
    except Exception:
        logger.exception(f"Entity extraction failed for doc {doc.id}")
        return {"entities": [], "relationships": []}


async def extract_and_store(
    doc: StoredDocument,
    llm: LLMClient,
    store: MemoryStore,
    graph: KnowledgeGraph,
    vector_store: VectorStore | None = None,
    embedding_client: EmbeddingClient | None = None,
) -> dict[str, int]:
    result = await extract_entities(doc, llm)
    entities_stored = 0
    relationships_stored = 0

    entity_name_to_id: dict[str, str] = {}

    for ent in result.get("entities", []):
        name = ent.get("name", "").strip()
        etype = ent.get("type", "topic").strip()
        desc = ent.get("description", "").strip()
        if not name:
            continue

        entity = Entity(
            id=None,
            name=name,
            entity_type=etype,
            description=desc,
            source_doc_id=doc.id,
        )
        await store.store_entity(entity)
        entities_stored += 1

        node_id = _make_node_id(name, etype)
        entity_name_to_id[name.lower()] = node_id
        graph.add_entity(GraphNode(
            id=node_id,
            entity_type=etype,
            name=name,
            properties={"description": desc, "source": doc.source, "doc_id": doc.id},
        ))

        if vector_store and vector_store.available and embedding_client:
            try:
                emb = await embedding_client.embed_entity(name, etype, desc)
                if emb:
                    await vector_store.add_entity(
                        entity_id=node_id,
                        embedding=emb,
                        text=f"{name} ({etype}): {desc}",
                        metadata={
                            "name": name,
                            "entity_type": etype,
                            "source": doc.source,
                        },
                    )
            except Exception as e:
                logger.debug(f"Entity embedding failed for {name}: {e}")

    for rel in result.get("relationships", []):
        src = rel.get("source", "").strip()
        tgt = rel.get("target", "").strip()
        relation = rel.get("relation", "related_to").strip()
        if not src or not tgt:
            continue

        src_id = entity_name_to_id.get(src.lower())
        tgt_id = entity_name_to_id.get(tgt.lower())
        if not src_id or not tgt_id:
            continue

        graph.add_relationship(GraphEdge(
            source_id=src_id,
            target_id=tgt_id,
            relation=relation,
            evidence=f"From: {doc.title} ({doc.source})",
        ))
        relationships_stored += 1

    await store.mark_processed(doc.id)

    return {"entities": entities_stored, "relationships": relationships_stored}
