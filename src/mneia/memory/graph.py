from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx

from mneia.config import DATA_DIR

GRAPH_DB_PATH = DATA_DIR / "graph.db"

GRAPH_SCHEMA = """
CREATE TABLE IF NOT EXISTS graph_nodes (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    properties TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS graph_edges (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    evidence TEXT DEFAULT '',
    PRIMARY KEY (source_id, target_id, relation),
    FOREIGN KEY (source_id) REFERENCES graph_nodes(id),
    FOREIGN KEY (target_id) REFERENCES graph_nodes(id)
);
"""


@dataclass
class GraphNode:
    id: str
    entity_type: str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    relation: str
    weight: float = 1.0
    evidence: str = ""


class KnowledgeGraph:
    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or GRAPH_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._graph = nx.DiGraph()
        self._init_db()
        self._load_from_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        try:
            conn.executescript(GRAPH_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _load_from_db(self) -> None:
        conn = self._get_conn()
        try:
            for row in conn.execute("SELECT * FROM graph_nodes"):
                self._graph.add_node(
                    row["id"],
                    entity_type=row["entity_type"],
                    name=row["name"],
                    properties=json.loads(row["properties"]),
                )
            for row in conn.execute("SELECT * FROM graph_edges"):
                self._graph.add_edge(
                    row["source_id"],
                    row["target_id"],
                    relation=row["relation"],
                    weight=row["weight"],
                    evidence=row["evidence"],
                )
        finally:
            conn.close()

    def add_entity(self, node: GraphNode) -> None:
        self._graph.add_node(
            node.id,
            entity_type=node.entity_type,
            name=node.name,
            properties=node.properties,
        )
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO graph_nodes (id, entity_type, name, properties)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    properties = excluded.properties
                """,
                (node.id, node.entity_type, node.name, json.dumps(node.properties)),
            )
            conn.commit()
        finally:
            conn.close()

    def add_relationship(self, edge: GraphEdge) -> None:
        self._graph.add_edge(
            edge.source_id,
            edge.target_id,
            relation=edge.relation,
            weight=edge.weight,
            evidence=edge.evidence,
        )
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO graph_edges (source_id, target_id, relation, weight, evidence)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_id, target_id, relation) DO UPDATE SET
                    weight = weight + excluded.weight,
                    evidence = excluded.evidence
                """,
                (edge.source_id, edge.target_id, edge.relation, edge.weight, edge.evidence),
            )
            conn.commit()
        finally:
            conn.close()

    def remove_node(self, node_id: str) -> None:
        if node_id in self._graph:
            self._graph.remove_node(node_id)
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM graph_edges WHERE source_id = ? OR target_id = ?", (node_id, node_id))
            conn.execute("DELETE FROM graph_nodes WHERE id = ?", (node_id,))
            conn.commit()
        finally:
            conn.close()

    def get_entities_by_type(self, entity_type: str) -> list[dict[str, Any]]:
        results = []
        for nid, data in self._graph.nodes(data=True):
            if data.get("entity_type") == entity_type:
                results.append({"id": nid, "name": data.get("name", ""), **data.get("properties", {})})
        return results

    def get_neighbors(self, node_id: str, depth: int = 1) -> dict[str, Any]:
        if node_id not in self._graph:
            return {"nodes": [], "edges": []}

        nodes_at_depth = {node_id}
        all_nodes = {node_id}
        for _ in range(depth):
            next_level: set[str] = set()
            for n in nodes_at_depth:
                next_level.update(self._graph.successors(n))
                next_level.update(self._graph.predecessors(n))
            nodes_at_depth = next_level - all_nodes
            all_nodes.update(nodes_at_depth)

        subgraph = self._graph.subgraph(all_nodes)
        nodes = []
        for n in subgraph.nodes(data=True):
            nodes.append({
                "id": n[0],
                "name": n[1].get("name", ""),
                "type": n[1].get("entity_type", ""),
            })

        edges = []
        for e in subgraph.edges(data=True):
            edges.append({
                "source": e[0],
                "target": e[1],
                "relation": e[2].get("relation", ""),
                "weight": e[2].get("weight", 1.0),
            })

        return {"nodes": nodes, "edges": edges}

    def get_stats(self) -> dict[str, Any]:
        type_counts: dict[str, int] = {}
        for _, data in self._graph.nodes(data=True):
            t = data.get("entity_type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "total_nodes": self._graph.number_of_nodes(),
            "total_edges": self._graph.number_of_edges(),
            "by_type": type_counts,
        }

    def export_json(self) -> dict[str, Any]:
        nodes = []
        for n, data in self._graph.nodes(data=True):
            nodes.append({"id": n, **data})
        edges = []
        for s, t, data in self._graph.edges(data=True):
            edges.append({"source": s, "target": t, **data})
        return {"nodes": nodes, "edges": edges}
