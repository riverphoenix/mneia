"""Interactive RLHF-style knowledge improvement session.

Walks through entities and relationships (most-connected first), asking
for validation or corrections.  All changes are applied immediately to the
knowledge graph and persisted to ~/.mneia/preferences.json so that future
LLM extraction runs can honour them.

No external UI dependencies — uses plain input() + Rich for styling.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mneia.config import MNEIA_DIR

console = Console()

PREFERENCES_PATH = MNEIA_DIR / "preferences.json"

_ENTITY_TYPES = (
    "person", "project", "topic", "decision",
    "belief", "meeting", "tool", "organization",
)
_RELATION_TYPES = (
    "works_with", "discussed_in", "decided_on", "related_to",
    "part_of", "uses", "manages", "reports_to", "met_with",
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_prefs() -> dict[str, Any]:
    if PREFERENCES_PATH.exists():
        try:
            return json.loads(PREFERENCES_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_prefs(prefs: dict[str, Any]) -> None:
    PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFERENCES_PATH.write_text(json.dumps(prefs, indent=2, default=str))


def _ask(prompt: str, valid: set[str]) -> str:
    """Prompt user for one character from *valid*.  Returns lowercase choice."""
    while True:
        try:
            resp = input(f"\n  {prompt}\n  → ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "q"
        if resp in valid:
            return resp
        console.print(f"    [yellow]Enter one of: {', '.join(sorted(valid))}[/yellow]")


def _ask_text(prompt: str) -> str:
    """Prompt for free text.  Returns empty string on interrupt."""
    try:
        return input(f"  {prompt}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _node_score(item: tuple[str, dict[str, Any]]) -> float:
    """Higher score = more important entity (shown first)."""
    nid, data = item
    return data.get("mention_count", 1)


# ── edge helpers ──────────────────────────────────────────────────────────────

def _update_relation(graph: Any, src: str, tgt: str, old_rel: str, new_rel: str) -> None:
    """Replace an edge relation in both the NetworkX graph and SQLite."""
    # In-memory update
    for u, v in ((src, tgt), (tgt, src)):
        if graph._graph.has_edge(u, v):
            data = graph._graph.edges[u, v]
            if data.get("relation") == old_rel:
                graph._graph.remove_edge(u, v)
                graph._graph.add_edge(u, v, **{**data, "relation": new_rel})
                break

    # SQLite update — relation is part of the PK so we replace the row
    db_path = graph._db_path
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM graph_edges WHERE (source_id=? AND target_id=? AND relation=?)"
            " OR (source_id=? AND target_id=? AND relation=?)",
            (src, tgt, old_rel, tgt, src, old_rel),
        ).fetchone()
        if row:
            conn.execute(
                "DELETE FROM graph_edges WHERE (source_id=? AND target_id=? AND relation=?)"
                " OR (source_id=? AND target_id=? AND relation=?)",
                (src, tgt, old_rel, tgt, src, old_rel),
            )
            conn.execute(
                "INSERT OR IGNORE INTO graph_edges "
                "(source_id, target_id, relation, weight, evidence, first_seen, last_seen) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    row["source_id"], row["target_id"], new_rel,
                    row["weight"], row["evidence"],
                    row["first_seen"], row["last_seen"],
                ),
            )
            conn.commit()
    finally:
        conn.close()


def _delete_edge(graph: Any, src: str, tgt: str, relation: str) -> None:
    """Remove an edge from both NetworkX and SQLite."""
    for u, v in ((src, tgt), (tgt, src)):
        if graph._graph.has_edge(u, v):
            if graph._graph.edges[u, v].get("relation") == relation:
                graph._graph.remove_edge(u, v)
                break

    db_path = graph._db_path
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "DELETE FROM graph_edges WHERE (source_id=? AND target_id=? AND relation=?)"
            " OR (source_id=? AND target_id=? AND relation=?)",
            (src, tgt, relation, tgt, src, relation),
        )
        conn.commit()
    finally:
        conn.close()


# ── main session ──────────────────────────────────────────────────────────────

def run_improve_session(graph: Any) -> None:
    """Run an interactive RLHF-style improvement session on the knowledge graph."""
    all_nodes = list(graph._graph.nodes(data=True))
    if not all_nodes:
        console.print("[yellow]Knowledge graph is empty. Run /extract first.[/yellow]")
        return

    # Most-mentioned / most-connected entities first
    all_nodes.sort(key=lambda item: -(item[1].get("mention_count", 1) + graph._graph.degree(item[0])))

    prefs = _load_prefs()
    session_changes = 0
    reviewed = 0
    total = len(all_nodes)

    console.print()
    console.print(Panel(
        "[bold cyan]Knowledge Improvement[/bold cyan]\n\n"
        "Review entities and relationships — validate, correct, or remove them.\n"
        "Changes are applied immediately and remembered for future syncs.\n\n"
        "[dim]  [1] keep  [2] update description  [3] delete  [s] skip  [q] quit[/dim]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print(f"  [dim]{total} entities to review. Press [cyan]q[/cyan] at any time to stop.[/dim]\n")

    for idx, (node_id, node_data) in enumerate(all_nodes):
        name = node_data.get("name", node_id)
        entity_type = node_data.get("entity_type", "unknown")
        props: dict[str, Any] = dict(node_data.get("properties", {}))
        description = props.get("description", "")
        mention_count = node_data.get("mention_count", 1)
        degree = graph._graph.degree(node_id)

        # Gather immediate connections (out + in)
        out_edges = [
            (tgt, graph._graph.edges[node_id, tgt])
            for tgt in graph._graph.successors(node_id)
        ]
        in_edges = [
            (src, graph._graph.edges[src, node_id])
            for src in graph._graph.predecessors(node_id)
        ]
        all_edges = (out_edges + in_edges)[:6]

        # ── Entity card ─────────────────────────────────────────────────────
        console.rule(f"[cyan][{idx + 1}/{total}][/cyan] {name}", style="dim")
        console.print(f"  [dim]type:[/dim] {entity_type}   [dim]mentions:[/dim] {mention_count}   [dim]connections:[/dim] {degree}")

        if description:
            console.print(f"  [dim]description:[/dim] {description[:200]}")

        extra = {k: v for k, v in props.items()
                 if k not in ("description", "source", "doc_id") and v}
        if extra:
            for k, v in list(extra.items())[:4]:
                console.print(f"  [dim]{k}:[/dim] {str(v)[:80]}")

        if all_edges:
            console.print()
            console.print("  [dim]Connections:[/dim]")
            for other_id, edata in all_edges[:4]:
                other_name = graph._graph.nodes.get(other_id, {}).get("name", other_id)
                rel = edata.get("relation", "related_to")
                console.print(f"    [cyan]{rel}[/cyan] → {other_name}")

        # ── Entity action ───────────────────────────────────────────────────
        choice = _ask(
            "[1] keep  [2] update  [3] delete  [s] skip  [q] quit",
            {"1", "2", "3", "s", "q"},
        )

        if choice == "q":
            break
        if choice == "s":
            continue

        reviewed += 1

        if choice == "3":
            confirm = _ask(f"Delete '{name}' permanently? [y/n]", {"y", "n"})
            if confirm == "y":
                graph.remove_node(node_id)
                prefs.setdefault("deleted_entities", [])
                if node_id not in prefs["deleted_entities"]:
                    prefs["deleted_entities"].append(node_id)
                console.print(f"  [yellow]✓ '{name}' deleted.[/yellow]")
                session_changes += 1
            continue

        if choice == "2":
            console.print(f"  [dim]Current:[/dim] {description or '(none)'}")
            new_desc = _ask_text("New description")
            if new_desc:
                props["description"] = new_desc
                graph.update_node_properties(node_id, props)
                prefs.setdefault("entity_descriptions", {})[node_id] = new_desc
                console.print(f"  [green]✓ Description updated.[/green]")
                session_changes += 1
            else:
                console.print("  [dim]Skipped (no input).[/dim]")

        # ── Relationship questions ───────────────────────────────────────────
        if all_edges and choice in ("1", "2"):
            rel_header_shown = False
            for other_id, edata in all_edges[:3]:
                other_name = graph._graph.nodes.get(other_id, {}).get("name", other_id)
                rel = edata.get("relation", "related_to")

                # Determine direction
                if graph._graph.has_edge(node_id, other_id):
                    src_id, tgt_id = node_id, other_id
                else:
                    src_id, tgt_id = other_id, node_id

                if not rel_header_shown:
                    console.print()
                    console.print("  [dim]Checking relationships…[/dim]")
                    rel_header_shown = True

                console.print()
                console.print(f"    [bold]{name}[/bold] [cyan]{rel}[/cyan] [bold]{other_name}[/bold]")
                rel_choice = _ask(
                    "[1] correct  [2] wrong relation  [3] not related  [s] skip",
                    {"1", "2", "3", "s"},
                )

                if rel_choice == "2":
                    console.print(f"    Valid relations: {', '.join(_RELATION_TYPES)}")
                    new_rel = _ask_text("New relation").lower()
                    if new_rel in _RELATION_TYPES:
                        _update_relation(graph, src_id, tgt_id, rel, new_rel)
                        prefs.setdefault("relation_corrections", {})[
                            f"{src_id}→{tgt_id}"
                        ] = new_rel
                        console.print(f"    [green]✓ Relation updated to '{new_rel}'.[/green]")
                        session_changes += 1
                    else:
                        console.print(f"    [yellow]Unknown relation, skipping.[/yellow]")

                elif rel_choice == "3":
                    _delete_edge(graph, src_id, tgt_id, rel)
                    prefs.setdefault("deleted_relations", [])
                    prefs["deleted_relations"].append(f"{src_id}→{tgt_id}:{rel}")
                    console.print(f"    [yellow]✓ Relationship removed.[/yellow]")
                    session_changes += 1

    # ── Save and summarise ───────────────────────────────────────────────────
    _save_prefs(prefs)

    console.print()
    console.print(Panel(
        f"[bold]Session complete[/bold]\n\n"
        f"  Reviewed : [cyan]{reviewed}[/cyan] entities\n"
        f"  Changes  : [green]{session_changes}[/green] applied\n"
        f"  Saved    : [dim]{PREFERENCES_PATH}[/dim]\n\n"
        f"[dim]Run [cyan]/context[/cyan] to regenerate context files with the corrections.[/dim]",
        border_style="green",
        padding=(1, 2),
    ))
