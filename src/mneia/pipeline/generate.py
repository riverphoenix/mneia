from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import jinja2

from mneia.config import TEMPLATES_DIR, MneiaConfig
from mneia.core.llm import LLMClient
from mneia.memory.graph import KnowledgeGraph
from mneia.memory.store import MemoryStore
from mneia.pipeline.summarize import generate_all_summaries

logger = logging.getLogger(__name__)

BUILTIN_TEMPLATES_DIR = Path(__file__).parent.parent / "context" / "templates"


def _get_template_env() -> jinja2.Environment:
    loaders = []
    if TEMPLATES_DIR.exists():
        loaders.append(jinja2.FileSystemLoader(str(TEMPLATES_DIR)))
    if BUILTIN_TEMPLATES_DIR.exists():
        loaders.append(jinja2.FileSystemLoader(str(BUILTIN_TEMPLATES_DIR)))
    return jinja2.Environment(
        loader=jinja2.ChoiceLoader(loaders),
        trim_blocks=True,
        lstrip_blocks=True,
    )


async def generate_context_files(
    config: MneiaConfig,
    store: MemoryStore,
    graph: KnowledgeGraph,
    llm: LLMClient,
    on_progress: Any | None = None,
) -> list[str]:
    output_dir = Path(config.context_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    env = _get_template_env()
    stats = await store.get_stats()
    graph_stats = graph.get_stats()
    graph_export = graph.export_json()

    summaries = await generate_all_summaries(
        store, llm, graph, on_progress=on_progress,
    )

    people = [
        {"name": data.get("name", ""), "type": data.get("entity_type", ""), **data.get("properties", {})}
        for _, data in graph._graph.nodes(data=True)
        if data.get("entity_type") == "person"
    ]
    projects = [
        {"name": data.get("name", ""), "type": data.get("entity_type", ""), **data.get("properties", {})}
        for _, data in graph._graph.nodes(data=True)
        if data.get("entity_type") == "project"
    ]
    topics = [
        {"name": data.get("name", ""), "type": data.get("entity_type", ""), **data.get("properties", {})}
        for _, data in graph._graph.nodes(data=True)
        if data.get("entity_type") == "topic"
    ]
    decisions = [
        {"name": data.get("name", ""), **data.get("properties", {})}
        for _, data in graph._graph.nodes(data=True)
        if data.get("entity_type") == "decision"
    ]
    beliefs = [
        {"name": data.get("name", ""), **data.get("properties", {})}
        for _, data in graph._graph.nodes(data=True)
        if data.get("entity_type") == "belief"
    ]

    context = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "stats": stats,
        "graph_stats": graph_stats,
        "summaries": summaries,
        "people": people,
        "projects": projects,
        "topics": topics,
        "decisions": decisions,
        "beliefs": beliefs,
        "overview": summaries.get("overview", ""),
        "graph_export": graph_export,
    }

    generated: list[str] = []
    template_files = [
        ("claude_md.j2", "CLAUDE.md"),
        ("people.j2", "people.md"),
        ("projects.j2", "projects.md"),
        ("decisions.j2", "decisions.md"),
        ("beliefs.j2", "beliefs.md"),
    ]

    for template_name, output_name in template_files:
        try:
            template = env.get_template(template_name)
            rendered = template.render(**context)
            out_path = output_dir / output_name
            out_path.write_text(rendered, encoding="utf-8")
            generated.append(output_name)
            logger.info(f"Generated {output_name}")
        except jinja2.TemplateNotFound:
            logger.warning(f"Template not found: {template_name}")
        except Exception:
            logger.exception(f"Failed to generate {output_name}")

    return generated
