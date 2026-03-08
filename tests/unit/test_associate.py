from __future__ import annotations

import pytest

from mneia.memory.graph import GraphEdge, GraphNode, KnowledgeGraph
from mneia.pipeline.associate import match_entities_by_name, merge_duplicate_entities


def test_match_exact():
    a = [{"name": "Alice"}]
    b = [{"name": "Alice"}]
    matches = match_entities_by_name(a, b)
    assert len(matches) == 1
    assert matches[0][2] == 1.0


def test_match_partial():
    a = [{"name": "Alice Smith"}]
    b = [{"name": "Alice"}]
    matches = match_entities_by_name(a, b)
    assert len(matches) == 1
    assert matches[0][2] == 0.7


def test_match_no_match():
    a = [{"name": "Alice"}]
    b = [{"name": "Bob"}]
    matches = match_entities_by_name(a, b)
    assert len(matches) == 0


def test_merge_duplicates(tmp_path):
    graph = KnowledgeGraph(db_path=tmp_path / "graph.db")

    graph.add_entity(GraphNode(id="person:alice", entity_type="person", name="Alice"))
    graph.add_entity(GraphNode(id="topic:alice", entity_type="topic", name="Alice"))
    graph.add_entity(GraphNode(id="project:falcon", entity_type="project", name="Falcon"))

    graph.add_relationship(GraphEdge(
        source_id="topic:alice", target_id="project:falcon", relation="works_on"
    ))

    merged = merge_duplicate_entities(graph)
    assert merged == 1
    assert graph._graph.number_of_nodes() == 2
    assert graph._graph.has_edge("person:alice", "project:falcon")
