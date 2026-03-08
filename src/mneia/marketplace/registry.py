from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from mneia.config import MNEIA_DIR

logger = logging.getLogger(__name__)

INDEX_URL = "https://raw.githubusercontent.com/riverphoenix/mneia/main/marketplace/index.json"
CACHE_FILE = MNEIA_DIR / "marketplace_index.json"
CACHE_TTL_SECONDS = 86400


@dataclass
class MarketplaceEntry:
    name: str
    display_name: str
    description: str
    version: str
    author: str
    package_name: str
    auth_type: str = ""
    tags: list[str] = field(default_factory=list)
    homepage: str = ""
    installed: bool = False


def _load_cache() -> dict[str, Any] | None:
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text())
        cached_at = data.get("cached_at", 0)
        if time.time() - cached_at > CACHE_TTL_SECONDS:
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(data: dict[str, Any]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["cached_at"] = time.time()
    CACHE_FILE.write_text(json.dumps(data, indent=2))


def fetch_index(force_refresh: bool = False) -> list[MarketplaceEntry]:
    if not force_refresh:
        cached = _load_cache()
        if cached:
            return _parse_entries(cached.get("connectors", []))

    try:
        resp = httpx.get(INDEX_URL, timeout=10, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        _save_cache(data)
        return _parse_entries(data.get("connectors", []))
    except Exception as e:
        logger.warning(f"Failed to fetch marketplace index: {e}")
        cached = _load_cache()
        if cached:
            return _parse_entries(cached.get("connectors", []))
        return _get_builtin_entries()


def search_index(query: str, entries: list[MarketplaceEntry] | None = None) -> list[MarketplaceEntry]:
    if entries is None:
        entries = fetch_index()

    query_lower = query.lower()
    scored: list[tuple[int, MarketplaceEntry]] = []

    for entry in entries:
        score = 0
        if query_lower in entry.name.lower():
            score += 10
        if query_lower in entry.display_name.lower():
            score += 8
        if query_lower in entry.description.lower():
            score += 3
        for tag in entry.tags:
            if query_lower in tag.lower():
                score += 5
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored]


def _parse_entries(raw: list[dict[str, Any]]) -> list[MarketplaceEntry]:
    entries = []
    installed = _get_installed_packages()
    for item in raw:
        entry = MarketplaceEntry(
            name=item.get("name", ""),
            display_name=item.get("display_name", ""),
            description=item.get("description", ""),
            version=item.get("version", "0.0.0"),
            author=item.get("author", ""),
            package_name=item.get("package_name", f"mneia-connector-{item.get('name', '')}"),
            auth_type=item.get("auth_type", ""),
            tags=item.get("tags", []),
            homepage=item.get("homepage", ""),
            installed=item.get("package_name", "") in installed,
        )
        entries.append(entry)
    return entries


def _get_installed_packages() -> set[str]:
    try:
        from importlib.metadata import distributions
        return {d.metadata["Name"] for d in distributions() if d.metadata["Name"].startswith("mneia-connector-")}
    except Exception:
        return set()


def _get_builtin_entries() -> list[MarketplaceEntry]:
    from mneia.connectors import get_available_connectors
    entries = []
    for m in get_available_connectors():
        entries.append(MarketplaceEntry(
            name=m.name,
            display_name=m.display_name,
            description=m.description,
            version=m.version,
            author=m.author,
            package_name=f"mneia (built-in)",
            auth_type=m.auth_type,
            tags=["built-in"],
            installed=True,
        ))
    return entries
