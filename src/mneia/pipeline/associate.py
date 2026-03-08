from __future__ import annotations

import logging
from typing import Any

from mneia.memory.graph import GraphEdge, KnowledgeGraph

logger = logging.getLogger(__name__)


def match_entities_by_name(
    entities_a: list[dict[str, Any]],
    entities_b: list[dict[str, Any]],
) -> list[tuple[str, str, float]]:
    matches = []
    for a in entities_a:
        a_name = a.get("name", "").lower().strip()
        for b in entities_b:
            b_name = b.get("name", "").lower().strip()
            if not a_name or not b_name:
                continue
            if a_name == b_name:
                matches.append((a.get("name", ""), b.get("name", ""), 1.0))
            elif a_name in b_name or b_name in a_name:
                matches.append((a.get("name", ""), b.get("name", ""), 0.7))
    return matches


def merge_duplicate_entities(graph: KnowledgeGraph) -> int:
    nodes = list(graph._graph.nodes(data=True))
    name_to_ids: dict[str, list[str]] = {}

    for node_id, data in nodes:
        name = data.get("name", "").lower().strip()
        if name:
            name_to_ids.setdefault(name, []).append(node_id)

    merged = 0
    for name, ids in name_to_ids.items():
        if len(ids) <= 1:
            continue
        canonical = ids[0]
        for dup_id in ids[1:]:
            for pred in list(graph._graph.predecessors(dup_id)):
                edge_data = graph._graph.edges[pred, dup_id]
                if not graph._graph.has_edge(pred, canonical):
                    graph.add_relationship(GraphEdge(
                        source_id=pred,
                        target_id=canonical,
                        relation=edge_data.get("relation", "related_to"),
                        weight=edge_data.get("weight", 1.0),
                        evidence=edge_data.get("evidence", ""),
                    ))
            for succ in list(graph._graph.successors(dup_id)):
                edge_data = graph._graph.edges[dup_id, succ]
                if not graph._graph.has_edge(canonical, succ):
                    graph.add_relationship(GraphEdge(
                        source_id=canonical,
                        target_id=succ,
                        relation=edge_data.get("relation", "related_to"),
                        weight=edge_data.get("weight", 1.0),
                        evidence=edge_data.get("evidence", ""),
                    ))
            graph.remove_node(dup_id)
            merged += 1

    logger.info(f"Merged {merged} duplicate entities")
    return merged
