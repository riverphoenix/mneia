from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from mneia.config import MneiaConfig
from mneia.core.agent import AgentResult, AgentState, BaseAgent
from mneia.core.connector import RawDocument
from mneia.core.llm import LLMClient
from mneia.memory.store import MemoryStore

logger = logging.getLogger(__name__)


class WebResearchAgent(BaseAgent):
    def __init__(self, config: MneiaConfig) -> None:
        super().__init__(
            name="web-research",
            description="Deep web research on a given topic",
        )
        self.config = config
        self._llm = LLMClient(config.llm)
        self._store = MemoryStore()

    async def run(self, **kwargs: Any) -> AgentResult:
        self._state = AgentState.RUNNING
        topic = kwargs.get("topic", "")
        max_pages = kwargs.get(
            "max_pages",
            self.config.enrichment_max_scrape_pages,
        )

        if not topic:
            self._state = AgentState.STOPPED
            return AgentResult(
                agent_name=self.name,
                errors=["No topic provided"],
            )

        try:
            result = await self._research(topic, max_pages)
            return result
        except Exception as e:
            logger.exception(f"Web research failed for '{topic}'")
            self._state = AgentState.ERROR
            return AgentResult(
                agent_name=self.name,
                errors=[str(e)],
            )
        finally:
            await self._llm.close()
            if self._state != AgentState.ERROR:
                self._state = AgentState.STOPPED

    async def stop(self) -> None:
        self._state = AgentState.STOPPED

    async def _research(
        self, topic: str, max_pages: int,
    ) -> AgentResult:
        urls = await self._search_urls(topic)
        if not urls:
            return AgentResult(
                agent_name=self.name,
                errors=["No URLs found for topic"],
            )

        scraped_pages = await self._scrape_pages(
            urls[:max_pages],
        )
        if not scraped_pages:
            return AgentResult(
                agent_name=self.name,
                errors=["Could not scrape any pages"],
            )

        summary = await self._synthesize(topic, scraped_pages)

        doc = RawDocument(
            source="web-research",
            source_id=f"research-{topic[:50].replace(' ', '-').lower()}",
            content=summary,
            content_type="research",
            title=f"Research: {topic}",
            timestamp=datetime.now(timezone.utc),
            url=urls[0] if urls else None,
            metadata={
                "topic": topic,
                "pages_scraped": len(scraped_pages),
                "source_urls": urls[:max_pages],
            },
        )

        doc_id = await self._store.store_document(doc)
        logger.info(
            f"Stored research on '{topic}' (doc_id={doc_id}, "
            f"{len(scraped_pages)} pages scraped)"
        )

        return AgentResult(
            agent_name=self.name,
            documents_processed=1,
            metadata={
                "topic": topic,
                "pages_scraped": len(scraped_pages),
                "doc_id": doc_id,
            },
        )

    async def _search_urls(self, topic: str) -> list[str]:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={
                        "q": topic,
                        "format": "json",
                        "no_html": 1,
                    },
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
                urls = []
                abstract_url = data.get("AbstractURL", "")
                if abstract_url:
                    urls.append(abstract_url)
                for t in data.get("RelatedTopics", [])[:10]:
                    if isinstance(t, dict):
                        url = t.get("FirstURL", "")
                        if url and url.startswith("http"):
                            urls.append(url)
                return urls
        except Exception as e:
            logger.warning(f"URL search failed for '{topic}': {e}")
            return []

    async def _scrape_pages(
        self, urls: list[str],
    ) -> list[dict[str, str]]:
        from mneia.connectors.web_scraper import scrape_url

        delay = self.config.enrichment_scrape_delay_seconds
        pages = []
        for url in urls:
            try:
                content = await scrape_url(
                    url, max_content_length=10000,
                )
                if content and len(content) > 50:
                    pages.append({"url": url, "content": content})
                if delay > 0:
                    await asyncio.sleep(delay)
            except Exception as e:
                logger.debug(f"Scrape failed for {url}: {e}")
        return pages

    async def _synthesize(
        self, topic: str, pages: list[dict[str, str]],
    ) -> str:
        context_parts = []
        for page in pages:
            context_parts.append(
                f"[Source: {page['url']}]\n{page['content'][:3000]}"
            )
        context = "\n\n---\n\n".join(context_parts)

        prompt = (
            f"Research topic: {topic}\n\n"
            f"Sources:\n{context}\n\n"
            "Based on these sources, provide a structured research "
            "summary with:\n"
            "1. Overview (2-3 sentences)\n"
            "2. Key findings (bullet points)\n"
            "3. Notable details\n"
            "4. Sources used\n\n"
            "Be factual and cite the sources."
        )

        try:
            return await self._llm.generate(prompt)
        except Exception as e:
            logger.warning(f"Synthesis failed: {e}")
            return "\n\n---\n\n".join(
                f"## {page['url']}\n{page['content'][:1000]}"
                for page in pages
            )
