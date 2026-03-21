from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_LABELS = [
    "person", "organization", "project", "tool",
    "location", "event", "date",
]

_model_cache: dict[str, Any] = {}


def _is_gliner_available() -> bool:
    try:
        from gliner import GLiNER  # noqa: F401
        return True
    except ImportError:
        return False


def _get_model(model_name: str = "urchade/gliner_base") -> Any:
    if model_name in _model_cache:
        return _model_cache[model_name]

    from gliner import GLiNER

    model = GLiNER.from_pretrained(model_name)
    _model_cache[model_name] = model
    return model


class NERExtractor:
    def __init__(self, model_name: str = "urchade/gliner_base") -> None:
        self._model_name = model_name
        self._available = _is_gliner_available()

    @property
    def available(self) -> bool:
        return self._available

    def extract(
        self,
        text: str,
        labels: list[str] | None = None,
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        if not self._available:
            return []

        if labels is None:
            labels = DEFAULT_LABELS

        try:
            model = _get_model(self._model_name)
            entities = model.predict_entities(text[:5000], labels, threshold=threshold)
            results = []
            seen: set[str] = set()
            for ent in entities:
                name = ent.get("text", ent.get("span", "")).strip()
                label = ent.get("label", "unknown").lower()
                score = ent.get("score", 0.0)
                if not name or len(name) < 2 or name.lower() in seen:
                    continue
                seen.add(name.lower())
                results.append({
                    "text": name,
                    "label": label,
                    "score": round(score, 3),
                })
            return sorted(results, key=lambda x: x["score"], reverse=True)
        except Exception:
            logger.debug("GLiNER extraction failed")
            return []
