"""Interactive CLI knowledge graph visualizer.

Uses Rich (already a dependency) — no additional packages required.
Navigation is menu-driven: users can browse entities by type, explore
relationship trees, view the graph overview, and search entities.

Optional: `pip install textual` for a richer TUI panel (auto-detected).
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

console = Console()

_TYPE_COLORS: dict[str, str] = {
    "person": "bright_cyan",
    "project": "bright_yellow",
    "topic": "bright_green",
    "decision": "bright_magenta",
    "belief": "bright_white",
    "meeting": "bright_blue",
    "tool": "green",
    "organization": "bright_red",
}

_ENTITY_TYPES = (
    "person", "project", "topic", "decision",
    "belief", "meeting", "tool", "organization",
)


def _color(entity_type: str) -> str:
    return _TYPE_COLORS.get(entity_type, "white")


def _ask(prompt: str) -> str:
    try:
        return input(f"\n  {prompt}\n  → ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "q"


# ── views ─────────────────────────────────────────────────────────────────────

def _show_overview(graph: Any) -> None:
    """Print graph-wide statistics and top entities."""
    stats = graph.get_stats()
    total_nodes = stats["total_nodes"]
    total_edges = stats["total_edges"]
    by_type: dict[str, int] = stats.get("by_type", {})

    console.print()
    console.print(Panel(
        f"[bold]Knowledge Graph Overview[/bold]\n\n"
        f"  Entities  : [cyan]{total_nodes}[/cyan]\n"
        f"  Relations : [cyan]{total_edges}[/cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))

    # Type breakdown table
    if by_type:
        tbl = Table(show_header=True, header_style="bold dim", box=None, padding=(0, 2))
        tbl.add_column("Type")
        tbl.add_column("Count", justify="right")
        tbl.add_column("Bar")
        max_count = max(by_type.values()) or 1
        for etype in _ENTITY_TYPES:
            cnt = by_type.get(etype, 0)
            if cnt == 0:
                continue
            bar_len = int(cnt / max_count * 20)
            bar = "█" * bar_len
            col = _color(etype)
            tbl.add_row(f"[{col}]{etype}[/{col}]", str(cnt), f"[{col}]{bar}[/{col}]")
        console.print(tbl)

    # Top entities by mention_count
    trending = graph.get_trending_entities(limit=10)
    if trending:
        console.print()
        console.print("  [bold dim]Most mentioned:[/bold dim]")
        for row in trending:
            try:
                props = row.get("properties", "{}")
                if isinstance(props, str):
                    props = __import__("json").loads(props)
            except Exception:
                props = {}
            etype = row.get("entity_type", "")
            name = row.get("name", row.get("id", "?"))
            mentions = row.get("mention_count", 1)
            col = _color(etype)
            console.print(
                f"    [{col}]{name}[/{col}] [dim]({etype}, {mentions}✕)[/dim]"
            )
    console.print()


def _show_entity_list(graph: Any, entity_type: str | None) -> list[tuple[str, dict[str, Any]]]:
    """Show a paginated table of entities.  Returns list of (node_id, data)."""
    if entity_type:
        nodes = [
            (nid, data)
            for nid, data in graph._graph.nodes(data=True)
            if data.get("entity_type") == entity_type
        ]
    else:
        nodes = list(graph._graph.nodes(data=True))

    # Sort by mention_count desc then name
    nodes.sort(key=lambda x: (-x[1].get("mention_count", 1), x[1].get("name", "")))

    if not nodes:
        console.print("  [dim]No entities found.[/dim]")
        return []

    label = entity_type or "all types"
    tbl = Table(
        show_header=True,
        header_style="bold dim",
        box=None,
        padding=(0, 2),
        title=f"Entities — {label} ({len(nodes)})",
    )
    tbl.add_column("#", justify="right", style="dim")
    tbl.add_column("Name")
    tbl.add_column("Type")
    tbl.add_column("Links", justify="right")
    tbl.add_column("Mentions", justify="right")
    tbl.add_column("Description", no_wrap=False, max_width=50)

    for i, (nid, data) in enumerate(nodes[:40], 1):
        name = data.get("name", nid)
        etype = data.get("entity_type", "")
        degree = graph._graph.degree(nid)
        mentions = data.get("mention_count", 1)
        props = data.get("properties", {})
        desc = props.get("description", "") if isinstance(props, dict) else ""
        col = _color(etype)
        tbl.add_row(
            str(i),
            f"[{col}]{name}[/{col}]",
            f"[dim]{etype}[/dim]",
            str(degree),
            str(mentions),
            f"[dim]{desc[:60]}[/dim]" if desc else "",
        )

    console.print()
    console.print(tbl)
    if len(nodes) > 40:
        console.print(f"  [dim](showing 40 of {len(nodes)})[/dim]")
    console.print()
    return nodes[:40]


def _build_relation_tree(graph: Any, node_id: str, depth: int = 2) -> Tree:
    """Build a Rich Tree showing relationships up to *depth* hops."""
    data = graph._graph.nodes.get(node_id, {})
    name = data.get("name", node_id)
    etype = data.get("entity_type", "")
    col = _color(etype)

    root = Tree(f"[bold {col}]{name}[/bold {col}] [dim]({etype})[/dim]")
    props = data.get("properties", {})
    if isinstance(props, dict):
        desc = props.get("description", "")
        if desc:
            root.add(f"[dim italic]{desc[:120]}[/dim italic]")

    _add_tree_edges(graph, root, node_id, depth=depth, visited={node_id})
    return root


def _add_tree_edges(
    graph: Any,
    tree: Tree,
    node_id: str,
    depth: int,
    visited: set[str],
) -> None:
    if depth == 0:
        return

    out_edges = [
        (tgt, graph._graph.edges[node_id, tgt])
        for tgt in graph._graph.successors(node_id)
        if tgt not in visited
    ]
    in_edges = [
        (src, graph._graph.edges[src, node_id])
        for src in graph._graph.predecessors(node_id)
        if src not in visited
    ]
    all_edges = out_edges + in_edges

    # Sort by edge weight
    all_edges.sort(key=lambda x: x[1].get("weight", 1.0), reverse=True)

    for other_id, edata in all_edges[:8]:
        other_data = graph._graph.nodes.get(other_id, {})
        other_name = other_data.get("name", other_id)
        other_type = other_data.get("entity_type", "")
        rel = edata.get("relation", "related_to")
        weight = edata.get("weight", 1.0)
        col = _color(other_type)
        w_str = f" [dim]×{weight:.0f}[/dim]" if weight > 1.5 else ""
        branch = tree.add(
            f"[cyan]{rel}[/cyan] → [{col}]{other_name}[/{col}] [dim]({other_type})[/dim]{w_str}"
        )
        if depth > 1:
            _add_tree_edges(graph, branch, other_id, depth - 1, visited | {node_id, other_id})


def _explore_entity(graph: Any, node_id: str) -> str | None:
    """Show full entity detail + relationship tree.  Returns next node_id or None."""
    data = graph._graph.nodes.get(node_id, {})
    if not data:
        console.print(f"  [yellow]Entity not found: {node_id}[/yellow]")
        return None

    name = data.get("name", node_id)
    etype = data.get("entity_type", "")
    props = data.get("properties", {})
    if not isinstance(props, dict):
        props = {}

    degree = graph._graph.degree(node_id)
    mentions = data.get("mention_count", 1)
    first_seen = data.get("first_seen", "")[:10]
    last_seen = data.get("last_seen", "")[:10]

    col = _color(etype)

    # Entity card
    meta_parts = [f"type: {etype}", f"connections: {degree}", f"mentions: {mentions}"]
    if first_seen:
        meta_parts.append(f"first seen: {first_seen}")
    if last_seen:
        meta_parts.append(f"last seen: {last_seen}")

    props_lines = []
    for k, v in props.items():
        if k not in ("description", "source", "doc_id") and v:
            props_lines.append(f"  [dim]{k}:[/dim] {str(v)[:100]}")

    body = f"[bold {col}]{name}[/bold {col}]\n" + "  ".join(meta_parts)
    if props.get("description"):
        body += f"\n\n  [italic]{props['description'][:300]}[/italic]"
    if props_lines:
        body += "\n" + "\n".join(props_lines[:6])

    console.print()
    console.print(Panel(body, border_style=col, padding=(1, 2)))

    # Relationship tree (depth 2)
    tree = _build_relation_tree(graph, node_id, depth=2)
    console.print(tree)

    # List immediate neighbours for navigation
    neighbours: list[tuple[str, str]] = []
    for tgt in graph._graph.successors(node_id):
        n = graph._graph.nodes.get(tgt, {}).get("name", tgt)
        neighbours.append((tgt, n))
    for src in graph._graph.predecessors(node_id):
        if src not in {nid for nid, _ in neighbours}:
            n = graph._graph.nodes.get(src, {}).get("name", src)
            neighbours.append((src, n))

    if neighbours:
        console.print()
        console.print("  [dim]Navigate to:[/dim]")
        for i, (nid, nname) in enumerate(neighbours[:9], 1):
            netype = graph._graph.nodes.get(nid, {}).get("entity_type", "")
            nc = _color(netype)
            console.print(f"    [{nc}][{i}] {nname}[/{nc}] [dim]({netype})[/dim]")
        console.print("    [dim][b] back   [q] menu[/dim]")

        choice = _ask("Navigate [1-9] / [b]ack / [q]uit")
        if choice.isdigit() and 1 <= int(choice) <= len(neighbours):
            return neighbours[int(choice) - 1][0]
        return None  # back or quit

    return None


def _search_entities(graph: Any) -> str | None:
    """Simple name-based entity search.  Returns node_id to explore or None."""
    query = _ask_text("Search entities (name contains)")
    if not query:
        return None

    q = query.lower()
    matches = [
        (nid, data)
        for nid, data in graph._graph.nodes(data=True)
        if q in data.get("name", "").lower()
    ]
    matches.sort(key=lambda x: x[1].get("mention_count", 1), reverse=True)

    if not matches:
        console.print("  [dim]No matches.[/dim]")
        return None

    console.print()
    for i, (nid, data) in enumerate(matches[:10], 1):
        name = data.get("name", nid)
        etype = data.get("entity_type", "")
        col = _color(etype)
        degree = graph._graph.degree(nid)
        console.print(f"    [{i}] [{col}]{name}[/{col}] [dim]({etype}, {degree} links)[/dim]")

    choice = _ask("Explore [1-N] / [b]ack")
    if choice.isdigit() and 1 <= int(choice) <= len(matches):
        return matches[int(choice) - 1][0]
    return None


def _ask_text(prompt: str) -> str:
    try:
        return input(f"  {prompt}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


# ── main session ──────────────────────────────────────────────────────────────

def run_visualize_session(graph: Any) -> None:
    """Run an interactive graph exploration session."""
    stats = graph.get_stats()
    if stats["total_nodes"] == 0:
        console.print("[yellow]Knowledge graph is empty. Run /extract first.[/yellow]")
        return

    console.print()
    console.print(Panel(
        "[bold cyan]Knowledge Graph Explorer[/bold cyan]\n\n"
        f"  {stats['total_nodes']} entities · {stats['total_edges']} relationships\n\n"
        "[dim]  Navigate your knowledge graph interactively.[/dim]",
        border_style="cyan",
        padding=(1, 2),
    ))

    nav_stack: list[str] = []  # entity navigation stack

    while True:
        if nav_stack:
            # We're inside an entity — show it
            node_id = nav_stack[-1]
            next_id = _explore_entity(graph, node_id)
            if next_id:
                nav_stack.append(next_id)
            else:
                nav_stack.pop()
            continue

        # Main menu
        console.print()
        console.print("  [bold]Menu[/bold]")
        console.print("  [1] Graph overview")
        console.print("  [2] Browse entities by type")
        console.print("  [3] Explore entity (by number)")
        console.print("  [4] Search entities")
        console.print("  [q] Exit visualizer")

        choice = _ask("[1-4] / [q]uit")

        if choice == "q":
            break

        elif choice == "1":
            _show_overview(graph)

        elif choice == "2":
            console.print()
            console.print("  [bold]Choose type:[/bold]")
            for i, t in enumerate(_ENTITY_TYPES, 1):
                cnt = graph.get_stats().get("by_type", {}).get(t, 0)
                if cnt:
                    col = _color(t)
                    console.print(f"    [{i}] [{col}]{t}[/{col}] [dim]({cnt})[/dim]")
            console.print(f"    [{len(_ENTITY_TYPES) + 1}] All")

            tc = _ask("Type number / [b]ack")
            if tc.isdigit():
                idx = int(tc) - 1
                if idx == len(_ENTITY_TYPES):
                    entities = _show_entity_list(graph, None)
                elif 0 <= idx < len(_ENTITY_TYPES):
                    entities = _show_entity_list(graph, _ENTITY_TYPES[idx])
                else:
                    entities = []

                if entities:
                    ec = _ask("Explore entity number / [b]ack")
                    if ec.isdigit() and 1 <= int(ec) <= len(entities):
                        nav_stack.append(entities[int(ec) - 1][0])

        elif choice == "3":
            # Browse all then pick by number
            entities = _show_entity_list(graph, None)
            if entities:
                ec = _ask("Explore entity number / [b]ack")
                if ec.isdigit() and 1 <= int(ec) <= len(entities):
                    nav_stack.append(entities[int(ec) - 1][0])

        elif choice == "4":
            node_id = _search_entities(graph)
            if node_id:
                nav_stack.append(node_id)

    console.print("[dim]  Visualizer closed.[/dim]\n")
