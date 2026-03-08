from __future__ import annotations

from pathlib import Path

import pytest

from mneia.memory.graph import GraphEdge, GraphNode, KnowledgeGraph


@pytest.fixture
def graph(tmp_path: Path) -> KnowledgeGraph:
    return KnowledgeGraph(db_path=tmp_path / "test_graph.db")


def test_add_entity(graph: KnowledgeGraph):
    node = GraphNode(id="person-1", entity_type="person", name="John Smith")
    graph.add_entity(node)

    stats = graph.get_stats()
    assert stats["total_nodes"] == 1
    assert stats["by_type"]["person"] == 1


def test_add_relationship(graph: KnowledgeGraph):
    graph.add_entity(GraphNode(id="person-1", entity_type="person", name="John"))
    graph.add_entity(GraphNode(id="project-1", entity_type="project", name="Alpha"))
    graph.add_relationship(GraphEdge(
        source_id="person-1",
        target_id="project-1",
        relation="works_on",
        weight=1.0,
    ))

    stats = graph.get_stats()
    assert stats["total_edges"] == 1


def test_get_neighbors(graph: KnowledgeGraph):
    graph.add_entity(GraphNode(id="p1", entity_type="person", name="Alice"))
    graph.add_entity(GraphNode(id="p2", entity_type="person", name="Bob"))
    graph.add_entity(GraphNode(id="proj1", entity_type="project", name="Alpha"))
    graph.add_relationship(GraphEdge(source_id="p1", target_id="proj1", relation="works_on"))
    graph.add_relationship(GraphEdge(source_id="p2", target_id="proj1", relation="works_on"))

    result = graph.get_neighbors("proj1", depth=1)
    assert len(result["nodes"]) == 3
    assert len(result["edges"]) == 2


def test_export_json(graph: KnowledgeGraph):
    graph.add_entity(GraphNode(id="p1", entity_type="person", name="Alice"))
    graph.add_entity(GraphNode(id="proj1", entity_type="project", name="Alpha"))
    graph.add_relationship(GraphEdge(source_id="p1", target_id="proj1", relation="leads"))

    export = graph.export_json()
    assert len(export["nodes"]) == 2
    assert len(export["edges"]) == 1


def test_persistence(tmp_path: Path):
    db_path = tmp_path / "persist_graph.db"

    graph1 = KnowledgeGraph(db_path=db_path)
    graph1.add_entity(GraphNode(id="p1", entity_type="person", name="Alice"))
    graph1.add_entity(GraphNode(id="proj1", entity_type="project", name="Alpha"))
    graph1.add_relationship(GraphEdge(source_id="p1", target_id="proj1", relation="leads"))

    graph2 = KnowledgeGraph(db_path=db_path)
    stats = graph2.get_stats()
    assert stats["total_nodes"] == 2
    assert stats["total_edges"] == 1
