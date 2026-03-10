from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mneia import __version__
from mneia.config import MNEIA_DIR, PID_PATH, MneiaConfig, ensure_dirs
from mneia.output import EXIT_INTERNAL_ERROR, get_output

app = typer.Typer(
    name="mneia",
    help="Autonomous multi-agent personal knowledge system",
    no_args_is_help=False,
    invoke_without_command=True,
    rich_markup_mode="rich",
)


def _version_callback(value: bool) -> None:
    if value:
        output = get_output()
        output.print(f"mneia v{__version__}")
        raise typer.Exit()


class _LazyConsole:
    """Proxy that delegates to the Output layer's Console.

    This ensures all existing console.print() calls respect NO_COLOR,
    --no-color, and other output configuration without changing 178 call sites.
    """

    def __getattr__(self, name: str) -> object:
        return getattr(get_output().console, name)


console = _LazyConsole()

BANNER = r"""
                         _
  _ __ ___  _ __   ___  (_) __ _
 | '_ ` _ \| '_ \ / _ \ | |/ _` |
 | | | | | | | | |  __/ | | (_| |
 |_| |_| |_|_| |_|\___| |_|\__,_|

"""


def _print_banner() -> None:
    output = get_output()
    output.print(Text(BANNER, style="bold cyan"))
    output.print(f"  v{__version__} — your personal knowledge agent\n", style="dim")


# --- Main callback: no args = interactive mode ---


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool | None = typer.Option(
        None, "--version", callback=_version_callback,
        is_eager=True, help="Show version and exit",
    ),
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output as JSON",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Show debug output",
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Suppress non-error output",
    ),
    no_input: bool = typer.Option(
        False, "--no-input", help="Disable interactive prompts",
    ),
    no_color: bool = typer.Option(
        False, "--no-color", help="Disable colored output",
    ),
) -> None:
    """Autonomous multi-agent personal knowledge system.

    Run with no arguments to enter interactive mode.
    Run with a command (e.g. mneia start) for direct execution.
    """
    output = get_output()
    output.configure(
        json_mode=json_output,
        verbose=verbose,
        quiet=quiet,
        no_input=no_input,
        no_color=no_color,
    )

    if ctx.invoked_subcommand is None:
        from mneia.interactive import run_interactive

        run_interactive()


# --- Top-level commands ---


@app.command()
def version() -> None:
    """Show mneia version."""
    output = get_output()
    if output.is_json:
        output.json_result({"version": __version__})
    else:
        console.print(f"mneia v{__version__}")


@app.command()
def start(
    detach: bool = typer.Option(False, "--detach", "-d", help="Run in background"),
    connectors: str | None = typer.Option(
        None, "--connectors", "-c", help="Comma-separated connector names"
    ),
    all_agents: bool = typer.Option(False, "--all", "-a", help="Start all agents"),
) -> None:
    """Start the mneia knowledge daemon."""
    import subprocess
    import time

    ensure_dirs()
    config = MneiaConfig.load()
    connector_filter = connectors.split(",") if connectors else None

    if detach:
        from mneia.config import MNEIA_DIR, PID_PATH, SOCKET_PATH

        if SOCKET_PATH.exists():
            console.print("[yellow]Daemon already running.[/yellow]")
            return

        python = sys.executable
        filter_arg = ""
        if connector_filter:
            filter_arg = f", connector_filter={connector_filter!r}"
        cmd = [
            python, "-c",
            "import asyncio, os; "
            f"open({str(PID_PATH)!r}, 'w').write(str(os.getpid())); "
            "from mneia.config import MneiaConfig; "
            "from mneia.core.lifecycle import AgentManager; "
            "config = MneiaConfig.load(); "
            f"manager = AgentManager(config{filter_arg}); "
            "asyncio.run(manager.run())"
        ]

        log_path = MNEIA_DIR / "logs" / "daemon.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(str(log_path), "a")
        devnull = open("/dev/null")

        proc = subprocess.Popen(
            cmd,
            stdin=devnull,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )

        PID_PATH.write_text(str(proc.pid))

        time.sleep(1.5)

        if SOCKET_PATH.exists():
            console.print(
                f"[green]● Daemon started[/green] [dim](PID {proc.pid})[/dim]"
            )
            console.print(f"  [dim]Logs: {log_path}[/dim]")
            console.print("  [dim]Stop with: [cyan]mneia stop[/cyan][/dim]")
        else:
            console.print(
                "[yellow]Daemon starting... check [cyan]mneia status[/cyan].[/yellow]"
            )
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
def stop(
    agent_name: str | None = typer.Argument(None, help="Stop specific agent (or omit for daemon)"),
    all_agents: bool = typer.Option(False, "--all", "-a", help="Stop all agents"),
) -> None:
    """Stop the mneia daemon or specific agents."""
    from mneia.core.lifecycle import send_command

    if agent_name and not all_agents:
        name = f"listener-{agent_name}" if not agent_name.startswith("listener-") else agent_name
        try:
            result = asyncio.run(send_command("stop_agent", name=name))
            if result.get("ok"):
                console.print(f"[yellow]Stopped agent: {result['stopped']}[/yellow]")
            elif result.get("error"):
                console.print(f"[red]{result['error']}[/red]")
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            console.print("[red]Daemon is not running.[/red]")
        return

    console.print("[yellow]Sending stop signal...[/yellow]")
    try:
        asyncio.run(send_command("stop"))
        console.print("[green]mneia stopped.[/green]")
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        if PID_PATH.exists():
            import os
            import signal as sig

            try:
                pid = int(PID_PATH.read_text().strip())
                os.kill(pid, sig.SIGTERM)
                console.print(f"[green]Sent SIGTERM to PID {pid}.[/green]")
            except (ProcessLookupError, ValueError):
                console.print("[dim]Stale PID file removed.[/dim]")
            PID_PATH.unlink(missing_ok=True)
        else:
            console.print("[red]mneia is not running.[/red]")


@app.command()
def status() -> None:
    """Show daemon status, agent states, and queue depth."""
    from mneia.core.lifecycle import send_command

    output = get_output()
    try:
        result = asyncio.run(send_command("status"))
        if result.get("running"):
            if output.is_json:
                output.json_result(result)
                return
            console.print(Panel("[green]mneia is running[/green]", title="Status"))
            table = Table(title="Agents")
            table.add_column("Agent", style="cyan")
            table.add_column("State", style="green")
            table.add_column("Docs Processed", justify="right")
            for agent in result.get("agents", []):
                table.add_row(
                    agent["name"], agent["state"],
                    str(agent.get("docs", 0)),
                )
            console.print(table)
        else:
            if output.is_json:
                output.json_result({"running": False})
                return
            console.print("[yellow]mneia is not running.[/yellow]")
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        if output.is_json:
            output.json_result({"running": False})
            return
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
    _llm_setup_wizard(config)

    context_dir = typer.prompt(
        "Context output directory",
        default=config.context_output_dir,
    )
    config.context_output_dir = context_dir

    config.save()
    console.print("\n[green]Configuration saved![/green]")
    _show_next_steps(config)


@config_app.command("llm")
def config_llm() -> None:
    """Configure LLM provider, API keys, and model selection."""
    ensure_dirs()
    config = MneiaConfig.load()

    console.print(Panel("LLM Configuration", title="Setup"))
    _llm_setup_wizard(config)
    config.save()
    console.print("\n[green]LLM configuration saved![/green]")
    console.print(f"  [dim]Provider:[/dim] [cyan]{config.llm.provider}[/cyan]")
    console.print(f"  [dim]Model:[/dim] [cyan]{config.llm.model}[/cyan]")


def _llm_setup_wizard(config: MneiaConfig) -> None:
    from mneia.core.llm_setup import (
        EMBEDDING_MODELS,
        PROVIDER_DISPLAY,
        get_models_for_provider,
    )

    console.print("\n[bold]Choose your LLM provider:[/bold]")
    providers = list(PROVIDER_DISPLAY.items())
    for i, (key, display) in enumerate(providers, 1):
        current = " [green](current)[/green]" if key == config.llm.provider else ""
        console.print(f"  [{i}] {display}{current}")

    choice = typer.prompt(
        "\nProvider number",
        default=str(next(
            i for i, (k, _) in enumerate(providers, 1)
            if k == config.llm.provider
        )),
    )
    try:
        provider_key = providers[int(choice) - 1][0]
    except (ValueError, IndexError):
        console.print("[red]Invalid choice, keeping current provider.[/red]")
        return

    config.llm.provider = provider_key

    if provider_key == "ollama":
        url = typer.prompt("Ollama base URL", default=config.llm.ollama_base_url)
        config.llm.ollama_base_url = url
        models = get_models_for_provider("ollama", url)
        if models:
            console.print("\n[bold]Available Ollama models:[/bold]")
            for i, m in enumerate(models, 1):
                current = " [green](current)[/green]" if m == config.llm.model else ""
                console.print(f"  [{i}] {m}{current}")
            model_choice = typer.prompt(
                "Model number or name", default=config.llm.model,
            )
            if model_choice.isdigit() and 1 <= int(model_choice) <= len(models):
                config.llm.model = models[int(model_choice) - 1]
            else:
                config.llm.model = model_choice
        else:
            console.print("[yellow]Ollama not reachable. Enter model name manually.[/yellow]")
            config.llm.model = typer.prompt("Model name", default=config.llm.model)
        config.llm.embedding_model = typer.prompt(
            "Embedding model", default=config.llm.embedding_model,
        )
    elif provider_key == "anthropic":
        if config.llm.anthropic_api_key:
            console.print(
                "[dim]Key already set. Enter new or press Enter to keep.[/dim]"
            )
        key = typer.prompt("Anthropic API key (sk-ant-...)", hide_input=True, default="")
        if key:
            config.llm.anthropic_api_key = key
        models = get_models_for_provider("anthropic")
        console.print("\n[bold]Available models:[/bold]")
        for i, m in enumerate(models, 1):
            console.print(f"  [{i}] {m}")
        model_choice = typer.prompt("Model number", default="1")
        if model_choice.isdigit() and 1 <= int(model_choice) <= len(models):
            config.llm.model = models[int(model_choice) - 1]
        config.llm.embedding_model = EMBEDDING_MODELS.get("anthropic", config.llm.embedding_model)
    elif provider_key == "openai":
        if config.llm.openai_api_key:
            console.print(
                "[dim]Key already set. Enter new or press Enter to keep.[/dim]"
            )
        key = typer.prompt("OpenAI API key (sk-...)", hide_input=True, default="")
        if key:
            config.llm.openai_api_key = key
        models = get_models_for_provider("openai")
        console.print("\n[bold]Available models:[/bold]")
        for i, m in enumerate(models, 1):
            console.print(f"  [{i}] {m}")
        model_choice = typer.prompt("Model number", default="1")
        if model_choice.isdigit() and 1 <= int(model_choice) <= len(models):
            config.llm.model = models[int(model_choice) - 1]
        config.llm.embedding_model = EMBEDDING_MODELS.get("openai", config.llm.embedding_model)
    elif provider_key == "google":
        if config.llm.google_api_key:
            console.print(
                "[dim]Key already set. Enter new or press Enter to keep.[/dim]"
            )
        key = typer.prompt("Google API key", hide_input=True, default="")
        if key:
            config.llm.google_api_key = key
        models = get_models_for_provider("google")
        console.print("\n[bold]Available models:[/bold]")
        for i, m in enumerate(models, 1):
            console.print(f"  [{i}] {m}")
        model_choice = typer.prompt("Model number", default="1")
        if model_choice.isdigit() and 1 <= int(model_choice) <= len(models):
            config.llm.model = models[int(model_choice) - 1]
        config.llm.embedding_model = EMBEDDING_MODELS.get("google", config.llm.embedding_model)

    console.print(
        f"\n[green]Selected:[/green] [cyan]{config.llm.provider}[/cyan] / "
        f"[cyan]{config.llm.model}[/cyan]"
    )


def _show_next_steps(config: MneiaConfig) -> None:
    enabled = [n for n, c in config.connectors.items() if c.enabled]
    console.print("\n[bold]Next steps:[/bold]")
    if not enabled:
        console.print("  1. Enable a connector: [cyan]mneia connector enable <name>[/cyan]")
        console.print("  2. Set it up: [cyan]mneia connector setup <name>[/cyan]")
        console.print("  3. Start the daemon: [cyan]mneia start -d[/cyan]")
    else:
        console.print(f"  [green]Connectors enabled:[/green] {', '.join(enabled)}")
        console.print("  1. Start the daemon: [cyan]mneia start -d[/cyan]")
        console.print("  2. Check status: [cyan]mneia status[/cyan]")
        console.print("  3. Ask a question: [cyan]mneia ask 'what do I know?'[/cyan]")
    console.print("  [dim]See all connectors: mneia connector list[/dim]")
    console.print("  [dim]Interactive mode: just run mneia[/dim]")


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

    output = get_output()
    available = get_available_connectors()

    if output.is_json:
        data = []
        for m in available:
            cc = config.connectors.get(m.name)
            data.append({
                "name": m.name,
                "display_name": m.display_name,
                "enabled": bool(cc and cc.enabled),
                "auth_type": m.auth_type,
            })
        output.json_result({"connectors": data})
        return

    table = Table(title="Connectors")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Status", style="green")
    table.add_column("Auth")

    for manifest in available:
        conn_config = config.connectors.get(manifest.name)
        enabled = conn_config and conn_config.enabled
        status_text = "[green]enabled[/green]" if enabled else "[dim]disabled[/dim]"
        table.add_row(
            manifest.name, manifest.display_name,
            status_text, manifest.auth_type,
        )

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
    """Run interactive setup for a connector with guided instructions."""
    config = MneiaConfig.load()
    from mneia.connectors import create_connector
    from mneia.core.llm_setup import get_connector_help

    connector = create_connector(name)
    if not connector:
        console.print(f"[red]Unknown connector: {name}[/red]")
        raise typer.Exit(1)

    help_info = get_connector_help(name)
    manifest = connector.manifest

    console.print(Panel(
        f"Setting up [cyan]{manifest.display_name}[/cyan]",
        title="Connector Setup",
    ))

    if help_info:
        console.print(f"\n  [bold]{manifest.display_name}[/bold]")
        console.print(f"  [dim]{help_info['description']}[/dim]\n")
        console.print("  [bold]Prerequisites:[/bold]")
        for line in help_info["prerequisites"].split("\n"):
            console.print(f"    {line}")
        console.print("\n  [bold]What you'll need:[/bold]")
        console.print(f"    {help_info['setup_help']}\n")
    else:
        console.print(f"\n  [dim]{manifest.description}[/dim]")
        console.print(f"  [dim]Auth: {manifest.auth_type}[/dim]\n")
        if manifest.required_config:
            console.print(f"  [bold]Required:[/bold] {', '.join(manifest.required_config)}")
        if manifest.optional_config:
            console.print(f"  [dim]Optional: {', '.join(manifest.optional_config)}[/dim]\n")

    if name not in config.connectors:
        from mneia.config import ConnectorConfig

        config.connectors[name] = ConnectorConfig(enabled=True)

    settings = connector.interactive_setup()
    config.connectors[name].settings = settings
    config.connectors[name].enabled = True
    config.save()

    console.print(f"\n[green]{manifest.display_name} configured and enabled![/green]")

    if help_info:
        console.print("\n[bold]Next steps:[/bold]")
        for line in help_info["next_steps"].split("\n"):
            console.print(f"  {line}")
    else:
        console.print("\nNext: [cyan]mneia start -d[/cyan] to begin syncing.")
    console.print()


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

    output = get_output()
    store = MemoryStore()
    stats = asyncio.run(store.get_stats())

    if output.is_json:
        output.json_result(stats)
        return

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

    output = get_output()
    store = MemoryStore()
    results = asyncio.run(store.search(query, limit=limit))

    if output.is_json:
        data = [
            {
                "title": doc.title,
                "source": doc.source,
                "content": doc.content[:500],
                "timestamp": doc.timestamp,
            }
            for doc in results
        ]
        output.json_result({"query": query, "results": data})
        return

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
    source: str | None = typer.Option(None, "--source", "-s", help="Purge only this source"),
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
    source: str | None = typer.Option(None, "--source", "-s", help="Limit to source"),
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
    entity_type: str | None = typer.Option(None, "--type", "-t", help="Filter by type"),
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


# --- Permission commands ---

permission_app = typer.Typer(help="Manage operation permissions")
app.add_typer(permission_app, name="permission")


@permission_app.command("grant")
def permission_grant(
    operation: str,
    ttl: int = typer.Option(24, "--ttl", help="Hours until expiry"),
) -> None:
    """Grant permission for a risky operation."""
    from mneia.core.permissions_db import PermissionsDB
    from mneia.core.safety import get_permission

    perm = get_permission(operation)
    if not perm:
        console.print(f"[red]Unknown operation: {operation}[/red]")
        from mneia.core.safety import list_permissions
        ops = [p.operation for p in list_permissions()]
        console.print(f"[dim]Available: {', '.join(ops)}[/dim]")
        raise typer.Exit(1)

    db = PermissionsDB()
    db.approve(operation, ttl_hours=ttl)
    console.print(
        f"[green]Granted '{operation}' for {ttl}h "
        f"(risk: {perm.risk_level.value})[/green]"
    )


@permission_app.command("revoke")
def permission_revoke(operation: str) -> None:
    """Revoke a previously granted permission."""
    from mneia.core.permissions_db import PermissionsDB

    db = PermissionsDB()
    db.revoke(operation)
    console.print(f"[yellow]Revoked: {operation}[/yellow]")


@permission_app.command("list")
def permission_list() -> None:
    """List all permissions and their approval status."""
    from mneia.core.permissions_db import PermissionsDB
    from mneia.core.safety import list_permissions

    db = PermissionsDB()
    approvals = {a["operation"]: a for a in db.list_approvals()}
    perms = list_permissions()

    table = Table(title="Permissions")
    table.add_column("Operation", style="cyan")
    table.add_column("Risk")
    table.add_column("Status")
    table.add_column("Expires")

    for perm in perms:
        risk_colors = {
            "low": "green",
            "medium": "yellow",
            "high": "red",
            "critical": "bold red",
        }
        color = risk_colors.get(perm.risk_level.value, "white")
        risk_text = f"[{color}]{perm.risk_level.value}[/{color}]"

        approval = approvals.get(perm.operation)
        if perm.risk_level.value == "low":
            status = "[green]auto-approved[/green]"
            expires = "-"
        elif approval:
            status = "[green]granted[/green]"
            exp = approval.get("expires_at", "")
            expires = exp[:19] if exp else "never"
        else:
            status = "[dim]not granted[/dim]"
            expires = "-"

        table.add_row(
            perm.operation, risk_text, status, expires,
        )

    console.print(table)


# --- MCP commands ---

mcp_app = typer.Typer(help="MCP server for AI tool integration")
app.add_typer(mcp_app, name="mcp")


@mcp_app.command("serve")
def mcp_serve() -> None:
    """Start the MCP server (stdio transport for Claude Code integration)."""
    try:
        from mneia.mcp.server import run_server
    except ImportError:
        console.print(
            "[red]MCP package not installed. "
            "Install with: pip install 'mneia[mcp]'[/red]"
        )
        raise typer.Exit(1)

    run_server()


# --- Marketplace commands ---

marketplace_app = typer.Typer(help="Browse and install connectors")
app.add_typer(marketplace_app, name="marketplace")


@marketplace_app.command("search")
def marketplace_search(query: str) -> None:
    """Search available connectors in the marketplace."""
    from mneia.marketplace.registry import search_index

    results = search_index(query)
    if not results:
        console.print(f"[yellow]No connectors found matching: {query}[/yellow]")
        return

    table = Table(title=f"Marketplace results for '{query}'")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Author", style="dim")
    table.add_column("Version")
    table.add_column("Status")

    for entry in results:
        status = "[green]installed[/green]" if entry.installed else "[dim]available[/dim]"
        table.add_row(entry.name, entry.description[:60], entry.author, entry.version, status)

    console.print(table)


@marketplace_app.command("install")
def marketplace_install(name: str) -> None:
    """Install a connector from the marketplace."""
    from mneia.marketplace.installer import install_connector, is_installed
    from mneia.marketplace.registry import fetch_index

    entries = fetch_index()
    entry = next((e for e in entries if e.name == name), None)

    if not entry:
        console.print(f"[red]Connector '{name}' not found in marketplace.[/red]")
        raise typer.Exit(1)

    if is_installed(entry.package_name):
        console.print(f"[yellow]{entry.package_name} is already installed.[/yellow]")
        return

    console.print(f"[cyan]Installing {entry.package_name}...[/cyan]")
    if install_connector(entry.package_name):
        console.print(f"[green]Installed {entry.display_name}![/green]")
        console.print(f"Enable it with: [cyan]mneia connector enable {name}[/cyan]")
    else:
        console.print("[red]Installation failed. Check logs for details.[/red]")
        raise typer.Exit(1)


@marketplace_app.command("list")
def marketplace_list_cmd() -> None:
    """List all available marketplace connectors."""
    from mneia.marketplace.registry import fetch_index

    entries = fetch_index()
    if not entries:
        console.print("[yellow]No connectors available.[/yellow]")
        return

    table = Table(title="Marketplace Connectors")
    table.add_column("Name", style="cyan")
    table.add_column("Display Name")
    table.add_column("Auth", style="dim")
    table.add_column("Tags", style="dim")
    table.add_column("Status")

    for entry in entries:
        status = "[green]installed[/green]" if entry.installed else "[dim]available[/dim]"
        tags = ", ".join(entry.tags) if entry.tags else ""
        table.add_row(entry.name, entry.display_name, entry.auth_type, tags, status)


# --- Agents TUI ---


@app.command()
def agents() -> None:
    """Interactive TUI dashboard for monitoring agents."""
    from mneia.tui import run_dashboard

    run_dashboard()


@app.command("agent-stats")
def agent_stats(
    agent: str | None = typer.Option(
        None, "--agent", "-a", help="Filter by agent name",
    ),
) -> None:
    """Show agent activity statistics for the last 24 hours."""
    from datetime import datetime

    from mneia.core.agent_stats import AgentStatsDB

    output = get_output()
    db = AgentStatsDB()
    stats = db.get_stats_24h()

    if output.is_json:
        filtered = {}
        for name, events in stats.items():
            if agent and agent not in name:
                continue
            filtered[name] = events
        recent = db.get_recent_events(agent_name=agent, limit=10)
        output.json_result({
            "agents": filtered,
            "recent_events": [
                {
                    "agent": ev.agent_name,
                    "event": ev.event_type,
                    "timestamp": ev.timestamp,
                    "details": ev.details,
                }
                for ev in recent
            ],
        })
        db.close()
        return

    if not stats:
        console.print("[dim]No agent activity in the last 24 hours.[/dim]")
        db.close()
        return

    table = Table(title="Agent Stats (Last 24h)")
    table.add_column("Agent", style="cyan")
    table.add_column("Starts", justify="right")
    table.add_column("Cycles", justify="right")
    table.add_column("Docs Processed", justify="right", style="green")
    table.add_column("Errors", justify="right", style="red")
    table.add_column("Restarts", justify="right", style="yellow")

    for agent_name, events in sorted(stats.items()):
        if agent and agent not in agent_name:
            continue
        table.add_row(
            agent_name,
            str(events.get("start", 0)),
            str(events.get("cycle", 0)),
            str(events.get("docs_processed", 0)),
            str(events.get("error", 0)),
            str(events.get("restart", 0)),
        )

    console.print(table)

    recent = db.get_recent_events(agent_name=agent, limit=10)
    if recent:
        console.print("\n[bold]Recent Events:[/bold]")
        for ev in recent:
            ts = datetime.fromtimestamp(ev.timestamp).strftime("%H:%M:%S")
            details = f" — {ev.details}" if ev.details else ""
            console.print(
                f"  [dim]{ts}[/dim] [{ev.agent_name}] "
                f"{ev.event_type}{details}"
            )

    db.close()


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
def menubar() -> None:
    """Launch macOS menu bar status icon."""
    try:
        from mneia.menubar import run_menubar
    except ImportError:
        console.print(
            "[red]rumps package not installed. "
            "Install with: pip install 'mneia[menubar]'[/red]"
        )
        raise typer.Exit(1)

    run_menubar()


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
    try:
        app()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        raise SystemExit(0)
    except Exception as e:
        output = get_output()
        output.error(f"Unexpected error: {e}")
        output.debug("Run with --verbose for full traceback")
        raise SystemExit(EXIT_INTERNAL_ERROR)
