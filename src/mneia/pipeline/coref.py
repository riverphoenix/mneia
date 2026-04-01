from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_coref_cache: dict[str, Any] = {}


def _is_fastcoref_available() -> bool:
    try:
        from fastcoref import FCoref  # noqa: F401
        return True
    except ImportError:
        return False


def resolve_coreferences(text: str) -> str:
    """Resolve pronouns and co-references to their canonical antecedents.

    Uses fastcoref for efficient in-document co-reference resolution.
    Returns the original text unchanged if fastcoref is not installed or fails.

    Example:
        "Alice joined HubSpot. She leads the Flywheel team."
        → "Alice joined HubSpot. Alice leads the Flywheel team."

    This improves downstream NER and entity extraction quality by making
    pronoun references explicit.
    """
    if not _is_fastcoref_available() or len(text.strip()) < 30:
        return text

    try:
        if "fcoref" not in _coref_cache:
            from fastcoref import FCoref
            _coref_cache["fcoref"] = FCoref()

        model = _coref_cache["fcoref"]
        preds = model.predict(texts=[text])

        if not preds:
            return text

        pred = preds[0]
        clusters = pred.get_clusters(as_strings=False)

        if not clusters:
            return text

        replacements: list[tuple[int, int, str]] = []
        for cluster in clusters:
            if len(cluster) < 2:
                continue
            canon_start, canon_end = cluster[0]
            canon_text = text[canon_start:canon_end]
            for start, end in cluster[1:]:
                span = text[start:end]
                # Only replace short pronouns / determiners, not longer noun phrases
                if len(span) <= 6 and span.lower() != canon_text.lower():
                    replacements.append((start, end, canon_text))

        if not replacements:
            return text

        replacements.sort(key=lambda x: x[0], reverse=True)
        chars = list(text)
        for start, end, rep in replacements:
            chars[start:end] = list(rep)

        return "".join(chars)

    except Exception as exc:
        logger.debug("Co-reference resolution failed: %s", exc)
        return text
