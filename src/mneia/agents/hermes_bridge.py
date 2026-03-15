from __future__ import annotations

import logging
import os
import sys
from typing import Any

from mneia.config import MNEIA_DIR, LLMConfig, MneiaConfig
from mneia.memory.graph import KnowledgeGraph
from mneia.memory.store import MemoryStore

logger = logging.getLogger(__name__)

HERMES_HOME = MNEIA_DIR / "hermes"

_hermes_path_patched = False


def _patch_hermes_path() -> None:
    global _hermes_path_patched  # noqa: PLW0603
    if _hermes_path_patched:
        return
    _hermes_path_patched = True
    try:
        import importlib.util

        spec = importlib.util.find_spec("run_agent")
        if spec and spec.origin:
            src_dir = os.path.dirname(os.path.abspath(spec.origin))
            if src_dir not in sys.path:
                sys.path.insert(0, src_dir)
                logger.debug("Added hermes source dir to sys.path: %s", src_dir)
    except Exception:
        pass


def is_hermes_available() -> bool:
    _patch_hermes_path()
    try:
        from run_agent import AIAgent  # noqa: F401
        return True
    except (ImportError, ModuleNotFoundError):
        return False


def _translate_llm_config(llm_config: LLMConfig) -> dict[str, Any]:
    provider = llm_config.provider
    model = llm_config.model

    if provider == "ollama":
        return {
            "model": f"ollama/{model}",
            "api_base": llm_config.ollama_base_url,
        }
    elif provider == "anthropic":
        return {
            "model": f"anthropic/{model}",
            "api_key": llm_config.anthropic_api_key,
        }
    elif provider == "openai":
        return {
            "model": model,
            "api_key": llm_config.openai_api_key,
        }
    elif provider == "google":
        return {
            "model": f"gemini/{model}",
            "api_key": llm_config.google_api_key,
        }
    return {"model": model}


def create_hermes_agent(
    config: MneiaConfig,
    store: MemoryStore,
    graph: KnowledgeGraph,
) -> Any:
    _patch_hermes_path()
    from run_agent import AIAgent

    from mneia.agents.hermes_tools import TOOL_DEFINITIONS, create_tool_handlers

    HERMES_HOME.mkdir(parents=True, exist_ok=True)
    os.environ["HERMES_HOME"] = str(HERMES_HOME)

    llm_params = _translate_llm_config(config.llm)
    model = llm_params.pop("model")

    tool_handlers = create_tool_handlers(store, graph)

    agent = AIAgent(
        model=model,
        tools=TOOL_DEFINITIONS,
        tool_handlers=tool_handlers,
        max_iterations=config.hermes_max_iterations,
        system_prompt=(
            "You are mneia's knowledge agent — a continuous learning system that "
            "processes the user's personal knowledge base (calendar events, emails, "
            "documents, notes, audio transcripts). Your job is to:\n"
            "1. Analyze new documents for key entities, relationships, and themes\n"
            "2. Build and maintain a knowledge graph of connections\n"
            "3. Generate cross-document insights and summaries\n"
            "4. Store valuable insights back into the knowledge base\n\n"
            "Use the provided tools to search, read, and write to the knowledge base. "
            "Be thorough but concise. Focus on actionable connections."
        ),
        **llm_params,
    )
    return agent


def run_hermes_cycle(
    agent: Any,
    doc_summaries: list[str],
) -> str | None:
    if not doc_summaries:
        return None

    prompt = (
        "I have new documents to process. Analyze them, extract entities and "
        "relationships, and store any insights. Here are the documents:\n\n"
        + "\n\n---\n\n".join(doc_summaries)
        + "\n\nUse the tools to:\n"
        "1. Search existing knowledge for related context\n"
        "2. Add new entities and connections to the graph\n"
        "3. Store any cross-document insights\n"
        "Summarize what you found and did."
    )

    try:
        response = agent.run_conversation(prompt)
        return response
    except Exception:
        logger.exception("hermes-agent conversation failed")
        return None
