from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mneia import __version__
from mneia.config import MNEIA_DIR, MneiaConfig, ensure_dirs

app = typer.Typer(
    name="mneia",
    help="Autonomous multi-agent personal knowledge system",
    no_args_is_help=False,
    invoke_without_command=True,
    rich_markup_mode="rich",
)
console = Console()

BANNER = r"""
                         _
  _ __ ___  _ __   ___  (_) __ _
 | '_ ` _ \| '_ \ / _ \ | |/ _` |
 | | | | | | | | |  __/ | | (_| |
 |_| |_| |_|_| |_|\___| |_|\__,_|

"""


def _print_banner() -> None:
    console.print(Text(BANNER, style="bold cyan"))
    console.print(f"  v{__version__} — your personal knowledge agent\n", style="dim")


# --- Main callback: no args = interactive mode ---


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """Autonomous multi-agent personal knowledge system.

    Run with no arguments to enter interactive mode.
    Run with a command (e.g. mneia start) for direct execution.
    """
    if ctx.invoked_subcommand is None:
        from mneia.interactive import run_interactive

        run_interactive()


# --- Top-level commands ---


@app.command()
def version() -> None:
    """Show mneia version."""
    console.print(f"mneia v{__version__}")


@app.command()
def start(
    detach: bool = typer.Option(False, "--detach", "-d", help="Run in background"),
    connectors: Optional[str] = typer.Option(
        None, "--connectors", "-c", help="Comma-separated connector names"
    ),
) -> None:
    """Start the mneia knowledge daemon."""
    import subprocess
    import time

    ensure_dirs()
    config = MneiaConfig.load()
    connector_filter = connectors.split(",") if connectors else None

    if detach:
        from mneia.config import MNEIA_DIR, SOCKET_PATH

        if SOCKET_PATH.exists():
            console.print("[yellow]Daemon already running.[/yellow]")
            return

        python = sys.executable
        filter_arg = ""
        if connector_filter:
            filter_arg = f", connector_filter={connector_filter!r}"
        cmd = [
            python, "-c",
            "import asyncio; from mneia.config import MneiaConfig; "
            "from mneia.core.lifecycle import AgentManager; "
            "config = MneiaConfig.load(); "
            f"manager = AgentManager(config{filter_arg}); "
            "asyncio.run(manager.run())"
        ]

        log_path = MNEIA_DIR / "logs" / "daemon.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(str(log_path), "a")

        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )

        time.sleep(1.5)

        if SOCKET_PATH.exists():
            console.print(f"[green]● Daemon started in background[/green] [dim](PID {proc.pid})[/dim]")
            console.print(f"  [dim]Logs: {log_path}[/dim]")
            console.print(f"  [dim]Stop with: [cyan]mneia stop[/cyan][/dim]")
        else:
            console.print("[yellow]Daemon starting... check [cyan]mneia status[/cyan] in a moment.[/yellow]")
        return

    _print_banner()
    from mneia.core.lifecycle import AgentManager

    manager = AgentManager(config, connector_filter=connector_filter)

    console.print("[green]Starting mneia...[/green]")
    console.print("[dim]Press Ctrl+C to stop  |  Run with -d to detach[/dim]\n")
    try:
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")


@app.command()
def stop() -> None:
    """Stop the mneia daemon."""
    console.print("[yellow]Sending stop signal...[/yellow]")
    from mneia.core.lifecycle import send_command

    try:
        asyncio.run(send_command("stop"))
        console.print("[green]mneia stopped.[/green]")
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        console.print("[red]mneia is not running.[/red]")


@app.command()
def status() -> None:
    """Show daemon status, agent states, and queue depth."""
    from mneia.core.lifecycle import send_command

    try:
        result = asyncio.run(send_command("status"))
        if result.get("running"):
            console.print(Panel("[green]mneia is running[/green]", title="Status"))
            table = Table(title="Agents")
            table.add_column("Agent", style="cyan")
            table.add_column("State", style="green")
            table.add_column("Docs Processed", justify="right")
            for agent in result.get("agents", []):
                table.add_row(agent["name"], agent["state"], str(agent.get("docs", 0)))
            console.print(table)
        else:
            console.print("[yellow]mneia is not running.[/yellow]")
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        console.print("[yellow]mneia is not running.[/yellow]")


# --- Config commands ---

config_app = typer.Typer(help="Manage mneia configuration")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show() -> None:
    """Show current configuration."""
    config = MneiaConfig.load()
    console.print_json(config.model_dump_json(indent=2))


@config_app.command("set")
def config_set(key: str, value: str) -> None:
    """Set a configuration value (dot-separated key path)."""
    config = MneiaConfig.load()
    try:
        config.set_value(key, value)
        console.print(f"[green]Set {key} = {value}[/green]")
    except (AttributeError, KeyError) as e:
        console.print(f"[red]Invalid key: {key} ({e})[/red]")
        raise typer.Exit(1)


@config_app.command("setup")
def config_setup() -> None:
    """Interactive setup wizard."""
    ensure_dirs()
    _print_banner()
    config = MneiaConfig.load()

    console.print(Panel("Welcome to mneia setup!", title="Setup Wizard"))

    provider = typer.prompt(
        "LLM provider (ollama/anthropic/openai)",
        default=config.llm.provider,
    )
    config.llm.provider = provider

    if provider == "ollama":
        model = typer.prompt("Ollama model for extraction", default=config.llm.model)
        config.llm.model = model
        embed = typer.prompt("Ollama embedding model", default=config.llm.embedding_model)
        config.llm.embedding_model = embed
        url = typer.prompt("Ollama base URL", default=config.llm.ollama_base_url)
        config.llm.ollama_base_url = url
    elif provider == "anthropic":
        key = typer.prompt("Anthropic API key", hide_input=True)
        config.llm.anthropic_api_key = key
        config.llm.model = "claude-sonnet-4-20250514"
    elif provider == "openai":
        key = typer.prompt("OpenAI API key", hide_input=True)
        config.llm.openai_api_key = key
        config.llm.model = "gpt-4o-mini"

    context_dir = typer.prompt(
        "Context output directory",
        default=config.context_output_dir,
    )
    config.context_output_dir = context_dir

    config.save()
    console.print("\n[green]Configuration saved![/green]")
    console.print("Next: enable a connector with [cyan]mneia connector enable <name>[/cyan]")


@config_app.command("reset")
def config_reset() -> None:
    """Reset configuration to defaults."""
    if typer.confirm("Reset all configuration to defaults?"):
        config = MneiaConfig()
        config.save()
        console.print("[green]Configuration reset.[/green]")


# --- Connector commands ---

connector_app = typer.Typer(help="Manage data connectors")
app.add_typer(connector_app, name="connector")


@connector_app.command("list")
def connector_list() -> None:
    """List available connectors and their status."""
    config = MneiaConfig.load()
    from mneia.connectors import get_available_connectors

    available = get_available_connectors()

    table = Table(title="Connectors")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Status", style="green")
    table.add_column("Auth")

    for manifest in available:
        conn_config = config.connectors.get(manifest.name)
        status_text = "[green]enabled[/green]" if conn_config and conn_config.enabled else "[dim]disabled[/dim]"
        table.add_row(manifest.name, manifest.display_name, status_text, manifest.auth_type)

    console.print(table)


@connector_app.command("enable")
def connector_enable(name: str) -> None:
    """Enable a connector."""
    config = MneiaConfig.load()
    from mneia.connectors import get_connector_manifest

    manifest = get_connector_manifest(name)
    if not manifest:
        console.print(f"[red]Unknown connector: {name}[/red]")
        raise typer.Exit(1)

    if name not in config.connectors:
        from mneia.config import ConnectorConfig

        config.connectors[name] = ConnectorConfig(
            enabled=True,
            poll_interval_seconds=manifest.poll_interval_seconds,
        )
    else:
        config.connectors[name].enabled = True

    config.save()
    console.print(f"[green]Enabled connector: {name}[/green]")
    console.print(f"Run [cyan]mneia connector setup {name}[/cyan] to configure it.")


@connector_app.command("disable")
def connector_disable(name: str) -> None:
    """Disable a connector."""
    config = MneiaConfig.load()
    if name in config.connectors:
        config.connectors[name].enabled = False
        config.save()
        console.print(f"[yellow]Disabled connector: {name}[/yellow]")
    else:
        console.print(f"[red]Connector not configured: {name}[/red]")


@connector_app.command("setup")
def connector_setup(name: str) -> None:
    """Run interactive setup for a connector."""
    config = MneiaConfig.load()
    from mneia.connectors import create_connector

    connector = create_connector(name)
    if not connector:
        console.print(f"[red]Unknown connector: {name}[/red]")
        raise typer.Exit(1)

    console.print(Panel(f"Setting up [cyan]{name}[/cyan]", title="Connector Setup"))

    if name not in config.connectors:
        from mneia.config import ConnectorConfig

        config.connectors[name] = ConnectorConfig(enabled=True)

    settings = connector.interactive_setup()
    config.connectors[name].settings = settings
    config.connectors[name].enabled = True
    config.save()
    console.print(f"[green]{name} configured and enabled![/green]")


@connector_app.command("sync")
def connector_sync(name: str) -> None:
    """Trigger immediate sync for a connector."""
    config = MneiaConfig.load()
    conn_config = config.connectors.get(name)
    if not conn_config or not conn_config.enabled:
        console.print(f"[red]Connector {name} is not enabled.[/red]")
        raise typer.Exit(1)

    from mneia.connectors import create_connector
    from mneia.pipeline.ingest import ingest_connector

    connector = create_connector(name)
    if not connector:
        console.print(f"[red]Unknown connector: {name}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Syncing {name}...[/cyan]")
    result = asyncio.run(ingest_connector(connector, conn_config, config))
    console.print(f"[green]Synced {result.documents_ingested} documents from {name}[/green]")

    if conn_config.last_checkpoint != result.checkpoint:
        conn_config.last_checkpoint = result.checkpoint
        config.save()


@connector_app.command("start-agent")
def connector_start_agent(name: str) -> None:
    """Start a connector's listener agent (daemon must be running)."""
    from mneia.core.lifecycle import send_command

    agent_name = f"listener-{name}" if not name.startswith("listener-") else name
    try:
        result = asyncio.run(send_command("start_agent", name=agent_name))
        if result.get("ok"):
            console.print(f"[green]Started agent: {result['started']}[/green]")
        elif result.get("error"):
            console.print(f"[red]{result['error']}[/red]")
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        console.print("[red]Daemon is not running. Start with: mneia start[/red]")


@connector_app.command("stop-agent")
def connector_stop_agent(name: str) -> None:
    """Stop a connector's listener agent."""
    from mneia.core.lifecycle import send_command

    agent_name = f"listener-{name}" if not name.startswith("listener-") else name
    try:
        result = asyncio.run(send_command("stop_agent", name=agent_name))
        if result.get("ok"):
            console.print(f"[yellow]Stopped agent: {result['stopped']}[/yellow]")
        elif result.get("error"):
            console.print(f"[red]{result['error']}[/red]")
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        console.print("[red]Daemon is not running.[/red]")


@connector_app.command("agents")
def connector_agents() -> None:
    """List running connector agents."""
    from mneia.core.lifecycle import send_command

    try:
        result = asyncio.run(send_command("list_agents"))
        agents = result.get("agents", [])
        if not agents:
            console.print("[dim]No agents running.[/dim]")
            return

        table = Table(title="Running Agents")
        table.add_column("Name", style="cyan")
        table.add_column("State", style="green")
        for a in agents:
            table.add_row(a["name"], a["state"])
        console.print(table)
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        console.print("[red]Daemon is not running.[/red]")


# --- Memory commands ---

memory_app = typer.Typer(help="Browse and search your knowledge")
app.add_typer(memory_app, name="memory")


@memory_app.command("stats")
def memory_stats() -> None:
    """Show memory statistics."""
    from mneia.memory.store import MemoryStore

    store = MemoryStore()
    stats = asyncio.run(store.get_stats())

    table = Table(title="Memory Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Total documents", str(stats.get("total_documents", 0)))
    table.add_row("Total entities", str(stats.get("total_entities", 0)))
    table.add_row("Total associations", str(stats.get("total_associations", 0)))

    if "by_source" in stats:
        table.add_section()
        for source, count in stats["by_source"].items():
            table.add_row(f"  {source}", str(count))

    console.print(table)


@memory_app.command("search")
def memory_search(
    query: str,
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
) -> None:
    """Full-text search across all stored knowledge."""
    from mneia.memory.store import MemoryStore

    store = MemoryStore()
    results = asyncio.run(store.search(query, limit=limit))

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    for doc in results:
        panel_content = doc.content[:500]
        if len(doc.content) > 500:
            panel_content += "..."
        console.print(
            Panel(
                panel_content,
                title=f"[cyan]{doc.title}[/cyan] [dim]({doc.source})[/dim]",
                subtitle=f"[dim]{doc.timestamp}[/dim]",
            )
        )


@memory_app.command("recent")
def memory_recent(
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
) -> None:
    """Show recently ingested items."""
    from mneia.memory.store import MemoryStore

    store = MemoryStore()
    results = asyncio.run(store.get_recent(limit=limit))

    if not results:
        console.print("[yellow]No documents stored yet.[/yellow]")
        return

    table = Table(title="Recent Documents")
    table.add_column("Title", style="cyan")
    table.add_column("Source")
    table.add_column("Type")
    table.add_column("Timestamp", style="dim")

    for doc in results:
        table.add_row(doc.title[:60], doc.source, doc.content_type, str(doc.timestamp))

    console.print(table)


@memory_app.command("purge")
def memory_purge(
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Purge only this source"),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation"),
) -> None:
    """Clear stored memory."""
    if not confirm:
        msg = f"Purge all data from {source}?" if source else "Purge ALL stored data?"
        if not typer.confirm(msg):
            raise typer.Abort()

    from mneia.memory.store import MemoryStore

    store = MemoryStore()
    asyncio.run(store.purge(source=source))
    console.print("[green]Memory purged.[/green]")


# --- Extract command ---


@app.command()
def extract(
    limit: int = typer.Option(50, "--limit", "-n", help="Max documents to process"),
) -> None:
    """Run entity extraction on unprocessed documents."""
    from mneia.core.llm import LLMClient
    from mneia.memory.graph import KnowledgeGraph
    from mneia.memory.store import MemoryStore
    from mneia.pipeline.extract import extract_and_store

    config = MneiaConfig.load()
    store = MemoryStore()
    graph = KnowledgeGraph()
    llm = LLMClient(config.llm)

    async def _run() -> None:
        docs = await store.get_unprocessed(limit=limit)
        if not docs:
            console.print("[dim]No unprocessed documents.[/dim]")
            return

        console.print(f"[cyan]Extracting entities from {len(docs)} documents...[/cyan]")
        total_entities = 0
        total_rels = 0

        for i, doc in enumerate(docs, 1):
            console.print(f"  [{i}/{len(docs)}] {doc.title[:60]}...", end="")
            try:
                result = await extract_and_store(doc, llm, store, graph)
                total_entities += result["entities"]
                total_rels += result["relationships"]
                console.print(f" [green]✓[/green] {result['entities']}E {result['relationships']}R")
            except Exception as e:
                console.print(f" [red]✗ {e}[/red]")

        console.print(f"\n[green]Extracted {total_entities} entities, {total_rels} relationships[/green]")
        stats = graph.get_stats()
        console.print(f"[dim]Graph now has {stats['total_nodes']} entities, {stats['total_edges']} relationships[/dim]")

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(llm.close())


# --- Context commands ---

context_app = typer.Typer(help="Manage generated context files")
app.add_typer(context_app, name="context")


@context_app.command("generate")
def context_generate() -> None:
    """Force regenerate all context .md files."""
    from mneia.core.llm import LLMClient
    from mneia.memory.graph import KnowledgeGraph
    from mneia.memory.store import MemoryStore
    from mneia.pipeline.generate import generate_context_files

    config = MneiaConfig.load()
    store = MemoryStore()
    graph = KnowledgeGraph()
    llm = LLMClient(config.llm)

    console.print("[cyan]Generating context files...[/cyan]")
    try:
        generated = asyncio.run(generate_context_files(config, store, graph, llm))
        if generated:
            for name in generated:
                console.print(f"  [green]✓[/green] {name}")
            console.print(f"\n[green]Generated {len(generated)} context file(s) in {config.context_output_dir}[/green]")
        else:
            console.print("[yellow]No files generated. Check templates and data.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
    finally:
        asyncio.run(llm.close())


@context_app.command("show")
def context_show() -> None:
    """List generated context files."""
    config = MneiaConfig.load()
    output_dir = Path(config.context_output_dir)
    if not output_dir.exists():
        console.print("[yellow]No context files generated yet.[/yellow]")
        return

    table = Table(title="Context Files")
    table.add_column("File", style="cyan")
    table.add_column("Size", justify="right")
    table.add_column("Modified", style="dim")

    for f in sorted(output_dir.glob("*.md")):
        stat = f.stat()
        size = f"{stat.st_size:,} bytes"
        from datetime import datetime

        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        table.add_row(f.name, size, modified)

    console.print(table)


@context_app.command("link")
def context_link(target_dir: str) -> None:
    """Symlink context files to a project directory."""
    config = MneiaConfig.load()
    source = Path(config.context_output_dir)
    target = Path(target_dir)

    if not source.exists():
        console.print("[red]No context files generated yet. Run mneia context generate first.[/red]")
        raise typer.Exit(1)

    target.mkdir(parents=True, exist_ok=True)
    for f in source.glob("*.md"):
        link = target / f.name
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(f)
        console.print(f"[green]Linked {f.name} -> {target}[/green]")


# --- Ask command ---


@app.command()
def ask(
    question: str,
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Limit to source"),
) -> None:
    """Ask a question about your knowledge (single query with RAG)."""
    from mneia.conversation import ConversationEngine

    config = MneiaConfig.load()
    engine = ConversationEngine(config)

    try:
        result = asyncio.run(engine.ask(question, source_filter=source))
        from rich.markdown import Markdown

        console.print()
        console.print(Markdown(result.answer))
        console.print()

        if result.citations:
            console.print("[dim]Sources:[/dim]")
            for cite in result.citations:
                console.print(f"  [dim]- {cite.title} ({cite.source})[/dim]")

        if result.suggested_followups:
            console.print("\n[dim]Follow-up questions:[/dim]")
            for q in result.suggested_followups:
                console.print(f"  [cyan]- {q}[/cyan]")
        console.print()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[dim]Ensure Ollama is running or an API key is configured.[/dim]")
    finally:
        asyncio.run(engine.close())


@app.command()
def chat() -> None:
    """Interactive multi-turn conversation about your knowledge."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.history import FileHistory
    from rich.markdown import Markdown

    from mneia.conversation import ConversationEngine

    config = MneiaConfig.load()
    engine = ConversationEngine(config)

    console.print("[cyan]Entering chat mode. Type 'exit' or Ctrl+D to leave.[/cyan]")
    console.print("[dim]Your conversation history is preserved across questions.[/dim]\n")

    session: PromptSession[str] = PromptSession(
        history=FileHistory(str(MNEIA_DIR / "chat_history.txt")),
    )

    try:
        while True:
            try:
                question = session.prompt(
                    HTML("<ansibrightcyan><b>you</b></ansibrightcyan> <ansigray>›</ansigray> "),
                )
                question = question.strip()
                if not question:
                    continue
                if question.lower() in ("exit", "quit", "/exit", "/quit"):
                    break
                if question.lower() in ("clear", "/clear"):
                    engine.clear_history()
                    console.print("[dim]Conversation cleared.[/dim]\n")
                    continue

                with console.status("[dim italic]Thinking...[/dim italic]", spinner="dots"):
                    result = asyncio.run(engine.ask(question))

                console.print()
                console.print(Markdown(result.answer))

                if result.citations:
                    console.print("\n[dim]Sources:[/dim]")
                    for cite in result.citations:
                        console.print(f"  [dim]- {cite.title} ({cite.source})[/dim]")

                if result.suggested_followups:
                    console.print("\n[dim]You could also ask:[/dim]")
                    for q in result.suggested_followups:
                        console.print(f"  [cyan]- {q}[/cyan]")
                console.print()

            except KeyboardInterrupt:
                console.print()
                continue
            except EOFError:
                break
    finally:
        asyncio.run(engine.close())
        console.print("\n[dim]Chat ended.[/dim]")


# --- Graph commands ---

graph_app = typer.Typer(help="Explore your knowledge graph")
app.add_typer(graph_app, name="graph")


@graph_app.command("show")
def graph_show() -> None:
    """Show knowledge graph summary."""
    from mneia.memory.graph import KnowledgeGraph

    graph = KnowledgeGraph()
    stats = graph.get_stats()

    table = Table(title="Knowledge Graph")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Total entities", str(stats["total_nodes"]))
    table.add_row("Total relationships", str(stats["total_edges"]))

    if stats.get("by_type"):
        table.add_section()
        for etype, count in sorted(stats["by_type"].items()):
            table.add_row(f"  {etype}", str(count))

    console.print(table)


@graph_app.command("entities")
def graph_entities(
    entity_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by type"),
) -> None:
    """List entities in the knowledge graph."""
    from mneia.memory.graph import KnowledgeGraph

    graph = KnowledgeGraph()

    table = Table(title="Entities")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Description", style="dim")

    for nid, data in graph._graph.nodes(data=True):
        etype = data.get("entity_type", "unknown")
        if entity_type and etype != entity_type:
            continue
        name = data.get("name", nid)
        desc = data.get("properties", {}).get("description", "")
        table.add_row(name, etype, desc[:80])

    console.print(table)


@graph_app.command("person")
def graph_person(name: str) -> None:
    """Show everything known about a person."""
    from mneia.memory.graph import KnowledgeGraph

    graph = KnowledgeGraph()
    node_id = f"person:{name.lower().replace(' ', '-')}"
    result = graph.get_neighbors(node_id, depth=2)

    if not result["nodes"]:
        console.print(f"[yellow]No person found matching: {name}[/yellow]")
        return

    console.print(Panel(f"[bold cyan]{name}[/bold cyan]", title="Person"))
    if result["edges"]:
        table = Table(show_header=True)
        table.add_column("Relationship", style="green")
        table.add_column("Entity", style="cyan")
        for edge in result["edges"]:
            other = edge["target"] if edge["source"] == node_id else edge["source"]
            other_name = other.split(":", 1)[-1].replace("-", " ").title()
            table.add_row(edge["relation"], other_name)
        console.print(table)


@graph_app.command("topic")
def graph_topic(name: str) -> None:
    """Show everything known about a topic."""
    from mneia.memory.graph import KnowledgeGraph

    graph = KnowledgeGraph()
    node_id = f"topic:{name.lower().replace(' ', '-')}"
    result = graph.get_neighbors(node_id, depth=2)

    if not result["nodes"]:
        console.print(f"[yellow]No topic found matching: {name}[/yellow]")
        return

    console.print(Panel(f"[bold cyan]{name}[/bold cyan]", title="Topic"))
    if result["edges"]:
        table = Table(show_header=True)
        table.add_column("Relationship", style="green")
        table.add_column("Entity", style="cyan")
        for edge in result["edges"]:
            other = edge["target"] if edge["source"] == node_id else edge["source"]
            other_name = other.split(":", 1)[-1].replace("-", " ").title()
            table.add_row(edge["relation"], other_name)
        console.print(table)


@graph_app.command("export")
def graph_export(
    fmt: str = typer.Option("json", "--format", "-f", help="Export format (json)"),
) -> None:
    """Export the knowledge graph."""
    import json as json_mod

    from mneia.memory.graph import KnowledgeGraph

    graph = KnowledgeGraph()
    data = graph.export_json()
    console.print_json(json_mod.dumps(data, indent=2, default=str))


# --- Marketplace commands ---

marketplace_app = typer.Typer(help="Browse and install connectors")
app.add_typer(marketplace_app, name="marketplace")


@marketplace_app.command("search")
def marketplace_search(query: str) -> None:
    """Search available connectors in the marketplace."""
    console.print("[yellow]Not yet implemented (Phase 9)[/yellow]")


@marketplace_app.command("install")
def marketplace_install(name: str) -> None:
    """Install a connector from the marketplace."""
    console.print("[yellow]Not yet implemented (Phase 9)[/yellow]")


@marketplace_app.command("list")
def marketplace_list_cmd() -> None:
    """List all available marketplace connectors."""
    console.print("[yellow]Not yet implemented (Phase 9)[/yellow]")


# --- Agents TUI ---


@app.command()
def agents() -> None:
    """Interactive TUI dashboard for monitoring agents."""
    from mneia.tui import run_dashboard

    run_dashboard()


# --- Logs & Update ---


@app.command()
def logs(
    level: str = typer.Option("info", "--level", "-l", help="Log level filter"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
) -> None:
    """Tail daemon logs."""
    import time

    from mneia.config import LOGS_DIR

    log_file = LOGS_DIR / "daemon.log"
    if not log_file.exists():
        console.print("[yellow]No log file found. Start the daemon first.[/yellow]")
        return

    level_upper = level.upper()
    level_priority = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "WARN": 2, "ERROR": 3, "CRITICAL": 4}
    min_priority = level_priority.get(level_upper, 1)

    def should_show(line: str) -> bool:
        for lname, lprio in level_priority.items():
            if lname in line.upper() and lprio >= min_priority:
                return True
        if min_priority <= 1:
            return True
        return False

    with open(str(log_file)) as f:
        all_lines = f.readlines()
        tail = all_lines[-lines:]
        for line in tail:
            if should_show(line):
                console.print(line.rstrip())

        if follow:
            console.print("[dim]Following logs... (Ctrl+C to stop)[/dim]")
            try:
                while True:
                    line = f.readline()
                    if line:
                        if should_show(line):
                            console.print(line.rstrip())
                    else:
                        time.sleep(0.5)
            except KeyboardInterrupt:
                console.print("\n[dim]Stopped.[/dim]")


@app.command()
def update() -> None:
    """Check for updates and install if available."""
    import httpx

    console.print("[cyan]Checking for updates...[/cyan]")
    try:
        resp = httpx.get(
            "https://api.github.com/repos/riverphoenix/mneia/releases/latest",
            timeout=5,
        )
        if resp.status_code == 200:
            latest = resp.json()["tag_name"].lstrip("v")
            if latest != __version__:
                console.print(f"[green]New version available: {latest} (current: {__version__})[/green]")
                console.print("Run: [cyan]pipx upgrade mneia[/cyan]")
            else:
                console.print(f"[green]You're on the latest version ({__version__})[/green]")
        else:
            console.print("[yellow]Could not check for updates.[/yellow]")
    except Exception:
        console.print("[yellow]Could not reach GitHub. Check your connection.[/yellow]")


# --- Entry point ---


def main() -> None:
    app()
