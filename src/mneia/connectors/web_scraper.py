from __future__ import annotations

import asyncio
import logging
from html.parser import HTMLParser

logger = logging.getLogger(__name__)

_RATE_LIMIT_DELAY = 1.0
_last_request_time = 0.0


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = False
        self._skip_tags = {"script", "style", "noscript", "nav", "footer", "header"}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._skip_tags:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in self._skip_tags:
            self._skip = False
        if tag in ("p", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li"):
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            text = data.strip()
            if text:
                self._parts.append(text)

    def get_text(self) -> str:
        raw = " ".join(self._parts)
        lines = [line.strip() for line in raw.split("\n")]
        return "\n".join(line for line in lines if line)


def extract_text_from_html(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.get_text()


async def _rate_limit() -> None:
    global _last_request_time
    import time
    now = time.monotonic()
    elapsed = now - _last_request_time
    if elapsed < _RATE_LIMIT_DELAY:
        await asyncio.sleep(_RATE_LIMIT_DELAY - elapsed)
    _last_request_time = time.monotonic()


async def scrape_url(url: str, max_content_length: int = 50000) -> str | None:
    content = await _scrape_crawl4ai(url)
    if content:
        return content[:max_content_length]

    content = await _scrape_httpx(url)
    if content:
        return content[:max_content_length]

    return None


async def _scrape_crawl4ai(url: str) -> str | None:
    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError:
        return None

    try:
        await _rate_limit()
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            if result and result.markdown:
                return result.markdown
    except Exception as e:
        logger.debug(f"crawl4ai failed for {url}: {e}")
    return None


async def _scrape_httpx(url: str) -> str | None:
    try:
        import httpx
    except ImportError:
        return None

    try:
        await _rate_limit()
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
        ) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; mneia/0.1; "
                        "+https://github.com/riverphoenix/mneia)"
                    ),
                },
            )
            if resp.status_code != 200:
                return None
            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type:
                return None
            return extract_text_from_html(resp.text)
    except Exception as e:
        logger.debug(f"httpx scrape failed for {url}: {e}")
    return None
