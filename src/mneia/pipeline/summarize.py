from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from mneia.core.llm import LLMClient
from mneia.memory.store import MemoryStore, StoredDocument

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM = """You are a personal knowledge summarizer.
Given a collection of documents, produce a concise summary that captures:
- Key people mentioned and their roles/context
- Important decisions or action items
- Main topics and themes
- Notable beliefs or opinions expressed
Be direct and factual. Use bullet points. Keep under 500 words."""

TOPIC_SUMMARY_SYSTEM = """You summarize documents about a specific topic.
Focus on: key points, decisions made, open questions, and action items.
Be direct, use bullet points, keep under 300 words."""

PERSON_SUMMARY_SYSTEM = """You summarize what is known about a specific person from documents.
Focus on: their role, relationship to the user, recent interactions, key discussions.
Be direct, use bullet points, keep under 200 words."""


async def summarize_documents(
    docs: list[StoredDocument],
    llm: LLMClient,
    system: str = SUMMARY_SYSTEM,
) -> str:
    if not docs:
        return ""

    doc_texts = []
    for doc in docs[:20]:
        snippet = doc.content[:1000]
        doc_texts.append(f"[{doc.title} — {doc.source}, {doc.timestamp[:10]}]\n{snippet}")

    combined = "\n\n---\n\n".join(doc_texts)
    prompt = f"Summarize these {len(docs)} documents:\n\n{combined}"

    try:
        return await llm.generate(prompt, system=system)
    except Exception:
        logger.exception("Summarization failed")
        return ""


async def generate_daily_summary(
    store: MemoryStore,
    llm: LLMClient,
    date: datetime | None = None,
) -> str:
    if date is None:
        date = datetime.now()

    start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    docs = await store.get_documents_in_range(start.isoformat(), end.isoformat())
    if not docs:
        return ""

    return await summarize_documents(docs, llm, system=SUMMARY_SYSTEM)


async def generate_topic_summary(
    store: MemoryStore,
    llm: LLMClient,
    topic: str,
) -> str:
    docs = await store.search(topic, limit=15)
    if not docs:
        return ""

    return await summarize_documents(docs, llm, system=TOPIC_SUMMARY_SYSTEM)


async def generate_person_summary(
    store: MemoryStore,
    llm: LLMClient,
    person_name: str,
) -> str:
    docs = await store.search(person_name, limit=15)
    if not docs:
        return ""

    return await summarize_documents(docs, llm, system=PERSON_SUMMARY_SYSTEM)


async def generate_all_summaries(
    store: MemoryStore,
    llm: LLMClient,
    graph: Any,
    max_people: int = 10,
    max_topics: int = 8,
    on_progress: Any | None = None,
) -> dict[str, str]:
    summaries: dict[str, str] = {}

    def _progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    recent = await store.get_recent(limit=30)
    if recent:
        _progress("Generating overview summary...")
        summaries["overview"] = await summarize_documents(recent, llm)

    people_nodes = [
        (nid, data) for nid, data in graph._graph.nodes(data=True)
        if data.get("entity_type") == "person"
    ]
    for i, (_nid, data) in enumerate(people_nodes[:max_people]):
        name = data.get("name", "")
        if name:
            _progress(f"Summarising person {i + 1}/{min(len(people_nodes), max_people)}: {name}")
            summary = await generate_person_summary(store, llm, name)
            if summary:
                summaries[f"person:{name}"] = summary

    topic_nodes = [
        (nid, data) for nid, data in graph._graph.nodes(data=True)
        if data.get("entity_type") in ("topic", "project")
    ]
    for i, (_nid, data) in enumerate(topic_nodes[:max_topics]):
        name = data.get("name", "")
        if name:
            _progress(f"Summarising topic {i + 1}/{min(len(topic_nodes), max_topics)}: {name}")
            summary = await generate_topic_summary(store, llm, name)
            if summary:
                summaries[f"topic:{name}"] = summary

    return summaries
