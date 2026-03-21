from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ENTITY_TYPES = Literal[
    "person", "project", "topic", "organization",
    "tool", "decision", "meeting", "belief",
]


class ExtractedEntity(BaseModel):
    name: str
    type: ENTITY_TYPES = "topic"
    description: str = ""
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class ExtractedRelationship(BaseModel):
    source: str
    target: str
    relation: str = "related_to"
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
    summary: str = ""


STRUCTURED_SYSTEM_PROMPT = (
    "You extract structured entities and relationships from personal documents. "
    "Return entities with their type and a brief description. "
    "Return relationships between extracted entities. "
    "Only extract clearly stated facts. Do not infer or hallucinate. "
    "Names should be proper nouns or specific identifiers. "
    "Keep descriptions under 30 words. "
    "Limit to the 10 most important entities per document. "
    "Relationships must reference entities you extracted."
)


def _is_instructor_available() -> bool:
    try:
        import instructor  # noqa: F401
        return True
    except ImportError:
        return False


async def extract_structured(
    title: str,
    source: str,
    content: str,
    content_type: str,
    llm_config: Any,
    ner_hints: list[dict[str, Any]] | None = None,
) -> ExtractionResult:
    if not _is_instructor_available():
        return ExtractionResult()

    import instructor
    import litellm

    client = instructor.from_litellm(litellm.acompletion)

    hint_text = ""
    if ner_hints:
        hint_lines = [f"  - {h['text']} ({h['label']}, score={h.get('score', '?')})" for h in ner_hints[:15]]
        hint_text = "\nPre-detected entities (use as hints, verify each):\n" + "\n".join(hint_lines) + "\n"

    user_prompt = (
        f"Extract entities and relationships from this {content_type}:\n\n"
        f"Title: {title}\nSource: {source}\n{hint_text}\n"
        f"Content:\n{content[:3000]}"
    )

    provider = llm_config.provider
    model = llm_config.model
    if provider == "ollama":
        model_name = f"ollama/{model}"
    elif provider == "anthropic":
        model_name = f"anthropic/{model}"
    elif provider == "google":
        model_name = f"gemini/{model}"
    else:
        model_name = model

    kwargs: dict[str, Any] = {"model": model_name, "temperature": 0.1}
    if provider == "anthropic" and llm_config.anthropic_api_key:
        kwargs["api_key"] = llm_config.anthropic_api_key
    elif provider == "openai" and llm_config.openai_api_key:
        kwargs["api_key"] = llm_config.openai_api_key
    elif provider == "google" and llm_config.google_api_key:
        kwargs["api_key"] = llm_config.google_api_key
    elif provider == "ollama":
        kwargs["api_base"] = llm_config.ollama_base_url

    try:
        result = await client.chat.completions.create(
            response_model=ExtractionResult,
            messages=[
                {"role": "system", "content": STRUCTURED_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_retries=2,
            **kwargs,
        )
        return result
    except Exception:
        logger.debug("Instructor extraction failed, returning empty result")
        return ExtractionResult()
