from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def match_entities_by_name(entities_a: list[dict[str, Any]], entities_b: list[dict[str, Any]]) -> list[tuple[str, str, float]]:
    matches = []
    for a in entities_a:
        a_name = a.get("name", "").lower().strip()
        for b in entities_b:
            b_name = b.get("name", "").lower().strip()
            if a_name == b_name:
                matches.append((a.get("name", ""), b.get("name", ""), 1.0))
            elif a_name in b_name or b_name in a_name:
                matches.append((a.get("name", ""), b.get("name", ""), 0.7))
    return matches
