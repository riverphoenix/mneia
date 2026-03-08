from __future__ import annotations

import asyncio
import logging
from typing import Any

from mneia.config import MneiaConfig
from mneia.core.agent import AgentResult, AgentState, BaseAgent
from mneia.core.llm import LLMClient
from mneia.memory.graph import KnowledgeGraph

logger = logging.getLogger(__name__)


class EnrichmentAgent(BaseAgent):
    def __init__(self, config: MneiaConfig) -> None:
        super().__init__(name="enrichment", description="Enriches entities with web data")
        self.config = config
        self._graph = KnowledgeGraph()
        self._llm = LLMClient(config.llm)
        self._running = False
        self._enriched_count = 0

    async def run(self, **kwargs: Any) -> AgentResult:
        self._running = True
        self._state = AgentState.RUNNING
        logger.info("Enrichment agent started")

        try:
            while self._running:
                enriched = await self._enrich_cycle()
                self._enriched_count += enriched
                await asyncio.sleep(300)
        except asyncio.CancelledError:
            pass
        finally:
            self._state = AgentState.STOPPED
            await self._llm.close()

        return AgentResult(
            agent_name=self.name,
            documents_processed=self._enriched_count,
        )

    async def stop(self) -> None:
        self._running = False

    async def _enrich_cycle(self) -> int:
        enriched = 0
        nodes_to_enrich = self._find_sparse_nodes()

        for node_id, data in nodes_to_enrich[:5]:
            name = data.get("name", "")
            entity_type = data.get("entity_type", "")
            existing_desc = data.get("properties", {}).get("description", "")

            if existing_desc and len(existing_desc) > 50:
                continue

            enrichment = await self._enrich_entity(name, entity_type)
            if enrichment:
                props = data.get("properties", {})
                props["description"] = enrichment.get("description", existing_desc)
                if enrichment.get("url"):
                    props["url"] = enrichment["url"]
                if enrichment.get("tags"):
                    props["tags"] = enrichment["tags"]

                self._graph.update_node_properties(node_id, props)
                enriched += 1
                logger.info(f"Enriched entity: {name}")

        return enriched

    def _find_sparse_nodes(self) -> list[tuple[str, dict[str, Any]]]:
        sparse = []
        for nid, data in self._graph._graph.nodes(data=True):
            desc = data.get("properties", {}).get("description", "")
            if not desc or len(desc) < 20:
                sparse.append((nid, data))
        return sparse

    async def _enrich_entity(self, name: str, entity_type: str) -> dict[str, Any] | None:
        web_info = await self._web_search(name, entity_type)

        if not web_info:
            return None

        prompt = (
            f"Given the following web search results about {entity_type} '{name}':\n\n"
            f"{web_info}\n\n"
            "Extract:\n"
            "1. A concise description (1-2 sentences)\n"
            "2. A relevant URL if available\n"
            "3. Up to 5 relevant tags\n\n"
            "Respond in this exact format:\n"
            "DESCRIPTION: <description>\n"
            "URL: <url or 'none'>\n"
            "TAGS: <comma-separated tags or 'none'>"
        )

        try:
            response = await self._llm.generate(prompt)
            return self._parse_enrichment_response(response)
        except Exception as e:
            logger.warning(f"LLM enrichment failed for {name}: {e}")
            return None

    async def _web_search(self, name: str, entity_type: str) -> str:
        try:
            import httpx

            query = f"{name} {entity_type}"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_html": 1},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    parts = []
                    abstract = data.get("Abstract", "")
                    if abstract:
                        parts.append(abstract)
                    for topic in data.get("RelatedTopics", [])[:3]:
                        if isinstance(topic, dict) and "Text" in topic:
                            parts.append(topic["Text"])
                    return "\n".join(parts) if parts else ""
        except Exception as e:
            logger.warning(f"Web search failed for {name}: {e}")
        return ""

    @staticmethod
    def _parse_enrichment_response(response: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("DESCRIPTION:"):
                result["description"] = line[len("DESCRIPTION:"):].strip()
            elif line.startswith("URL:"):
                url = line[len("URL:"):].strip()
                if url.lower() != "none" and url.startswith("http"):
                    result["url"] = url
            elif line.startswith("TAGS:"):
                tags_str = line[len("TAGS:"):].strip()
                if tags_str.lower() != "none":
                    result["tags"] = [t.strip() for t in tags_str.split(",") if t.strip()]
        return result
