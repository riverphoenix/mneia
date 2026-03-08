from __future__ import annotations

import logging
from typing import Any

from mneia.core.llm import LLMClient
from mneia.memory.store import Entity, StoredDocument

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """You extract structured entities from documents.
Return JSON with: {"entities": [{"name": "...", "type": "person|project|topic|decision|belief|meeting", "description": "..."}], "relationships": [{"source": "...", "target": "...", "relation": "..."}]}
Only extract clearly stated facts. Do not infer or hallucinate."""


async def extract_entities(
    doc: StoredDocument,
    llm: LLMClient,
) -> dict[str, Any]:
    prompt = f"""Extract entities and relationships from this {doc.content_type}:

Title: {doc.title}
Source: {doc.source}
Content:
{doc.content[:3000]}"""

    try:
        result = await llm.generate_json(prompt, system=EXTRACTION_SYSTEM_PROMPT)
        return result
    except Exception:
        logger.exception(f"Entity extraction failed for doc {doc.id}")
        return {"entities": [], "relationships": []}
