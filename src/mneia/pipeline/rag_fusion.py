from __future__ import annotations

from typing import Any

_RRF_K = 60  # Standard constant from Cormack et al. 2009


def reciprocal_rank_fusion(
    result_lists: list[list[Any]],
    id_fn: Any = None,
    k: int = _RRF_K,
) -> list[Any]:
    """Merge multiple ranked result lists using Reciprocal Rank Fusion.

    RRF(d) = Σ 1 / (k + rank(d)) summed over all lists containing d.

    Documents appearing in more lists and at higher ranks score higher.
    k=60 is the standard value — higher k gives more weight to lower-ranked docs.

    Args:
        result_lists: Ranked lists of docs. Index 0 = highest rank.
        id_fn:        Callable(item) → stable key. Defaults to item.id or id(item).
        k:            Smoothing constant.

    Returns:
        Single merged list sorted by descending RRF score.
    """
    if not result_lists:
        return []

    if id_fn is None:
        def id_fn(x: Any) -> Any:  # type: ignore[misc]
            return getattr(x, "id", id(x))

    scores: dict[Any, float] = {}
    items: dict[Any, Any] = {}

    for result_list in result_lists:
        for rank, item in enumerate(result_list, start=1):
            key = id_fn(item)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            items[key] = item

    sorted_keys = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [items[key] for key in sorted_keys]
