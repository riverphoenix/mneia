from __future__ import annotations

import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mneia import __version__
from mneia.config import MNEIA_DIR, MneiaConfig, ensure_dirs

logger = logging.getLogger(__name__)
console = Console()

BANNER = r"""[bold cyan]
                         _
  _ __ ___  _ __   ___  (_) __ _
 | '_ ` _ \| '_ \ / _ \ | |/ _` |
 | | | | | | | | |  __/ | | (_| |
 |_| |_| |_|_| |_|\___| |_|\__,_|
[/bold cyan]"""

SLASH_COMMANDS: dict[str, dict[str, str]] = {
    "/help": {"desc": "Show all available commands", "alias": ""},
    "/status": {"desc": "Show daemon and agent status", "alias": ""},
    "/search": {"desc": "Search your knowledge — /search <query>", "alias": ""},
    "/ask": {"desc": "Ask a question with RAG — /ask <question>", "alias": ""},
    "/stats": {"desc": "Show memory statistics", "alias": ""},
    "/agent-stats": {"desc": "Show agent activity stats (last 24h)", "alias": ""},
    "/recent": {"desc": "Show recently ingested documents", "alias": ""},
    "/connectors": {"desc": "List connectors and their status", "alias": ""},
    "/connector-setup": {"desc": "Interactive connector setup — /connector-setup <name>", "alias": ""},
    "/sync": {"desc": "Sync a connector — /sync <name>", "alias": ""},
    "/connector-start": {"desc": "Start a connector agent — /connector-start <name>", "alias": ""},
    "/connector-stop": {"desc": "Stop a connector agent — /connector-stop <name>", "alias": ""},
    "/agents": {"desc": "List running agents", "alias": ""},
    "/start": {"desc": "Start daemon or agents — /start [all|agent_name]", "alias": ""},
    "/stop": {"desc": "Stop daemon or agents — /stop [all|agent_name]", "alias": ""},
    "/extract": {"desc": "Run entity extraction — /extract [limit]", "alias": ""},
    "/graph": {"desc": "Show knowledge graph summary", "alias": ""},
    "/graph-entities": {"desc": "List entities — /graph-entities [type]", "alias": ""},
    "/graph-person": {"desc": "Show person info — /graph-person <name>", "alias": ""},
    "/graph-topic": {"desc": "Show topic info — /graph-topic <name>", "alias": ""},
    "/context": {"desc": "Generate context .md files", "alias": ""},
    "/config": {"desc": "Show current configuration", "alias": ""},
    "/config-llm": {"desc": "Configure LLM provider, API keys, and model", "alias": ""},
    "/logs": {"desc": "Show recent daemon logs — /logs [level]", "alias": ""},
    "/chat": {"desc": "Enter multi-turn chat mode", "alias": ""},
    "/clear": {"desc": "Clear the screen", "alias": ""},
    "/exit": {"desc": "Exit mneia", "alias": "/quit"},
}

THINKING_PHRASES = [
    "Searching through your knowledge...",
    "Connecting the dots...",
    "Thinking about that...",
    "Looking through your notes...",
    "Reasoning about your question...",
    "Pulling together what I know...",
]


def _get_thinking_phrase() -> str:
    import random

    return random.choice(THINKING_PHRASES)


class InteractiveSession:
    def __init__(self) -> None:
        ensure_dirs()
        self.config = MneiaConfig.load()
        self._ollama_available: bool | None = None
        self._history_file = MNEIA_DIR / "history.txt"
        self._conversation_engine: Any = None
        self._completer = WordCompleter(
            list(SLASH_COMMANDS.keys()) + ["/quit", "/chat"],
            sentence=True,
        )

    def run(self) -> None:
        console.print(BANNER)
        console.print(f"  [dim]v{__version__} — your personal knowledge agent[/dim]")
        console.print("  [dim]Type [cyan]/help[/cyan] for commands or just ask a question.[/dim]\n")

        self._check_ollama_status()
        self._show_quick_status()

        session: PromptSession[str] = PromptSession(
            history=FileHistory(str(self._history_file)),
            completer=self._completer,
            complete_while_typing=False,
        )

        while True:
            try:
                user_input = session.prompt(
                    HTML("<ansibrightcyan><b>mneia</b></ansibrightcyan> <ansigray>›</ansigray> "),
                )
                user_input = user_input.strip()
                if not user_input:
                    continue

                if user_input.startswith("/"):
                    if not self._handle_command(user_input):
                        break
                else:
                    self._handle_conversation(user_input)

            except KeyboardInterrupt:
                console.print()
                continue
            except EOFError:
                console.print("\n[dim]Goodbye.[/dim]")
                break
            except Exception as e:
                console.print(f"\n[red]Error: {e}[/red]\n")
                continue

    def _check_ollama_status(self) -> None:
        provider = self.config.llm.provider

        if provider != "ollama":
            has_key = (
                (provider == "anthropic" and self.config.llm.anthropic_api_key)
                or (provider == "openai" and self.config.llm.openai_api_key)
                or (provider == "google" and self.config.llm.google_api_key)
            )
            if has_key:
                self._ollama_available = True
                model = self.config.llm.model
                console.print(
                    f"  [green]●[/green] [dim]LLM ready"
                    f" ([cyan]{model}[/cyan] via {provider})[/dim]"
                )
            else:
                self._ollama_available = False
                console.print(
                    f"  [red]●[/red] [dim]No API key configured for {provider}[/dim]"
                )
                console.print(
                    "    [dim]Run [cyan]/config[/cyan] to set your API key[/dim]"
                )
            return

        import httpx

        try:
            resp = httpx.get(
                f"{self.config.llm.ollama_base_url}/api/tags",
                timeout=3,
            )
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m["name"] for m in models]
                has_model = any(
                    self.config.llm.model in name for name in model_names
                )
                if has_model:
                    self._ollama_available = True
                    console.print(
                        f"  [green]●[/green] [dim]LLM ready ([cyan]{self.config.llm.model}[/cyan] via Ollama)[/dim]"
                    )
                else:
                    self._ollama_available = False
                    console.print(
                        f"  [yellow]●[/yellow] [dim]Ollama running but model [cyan]{self.config.llm.model}[/cyan] not found[/dim]"
                    )
                    console.print(
                        f"    [dim]Run: [cyan]ollama pull {self.config.llm.model}[/cyan][/dim]"
                    )
            else:
                self._ollama_available = False
        except Exception:
            self._ollama_available = False
            console.print(
                "  [red]●[/red] [dim]Ollama not running — conversational mode unavailable[/dim]"
            )
            console.print("    [dim]To enable, install and start Ollama:[/dim]")
            console.print("    [dim]  brew install ollama[/dim]")
            console.print("    [dim]  ollama serve[/dim]")
            console.print(
                f"    [dim]  ollama pull {self.config.llm.model}[/dim]"
            )

    def _show_quick_status(self) -> None:
        from mneia.memory.store import MemoryStore

        store = MemoryStore()
        stats = asyncio.run(store.get_stats())
        total = stats.get("total_documents", 0)

        enabled_connectors = [
            n for n, c in self.config.connectors.items() if c.enabled
        ]

        parts = []
        if total > 0:
            parts.append(f"[green]{total}[/green] documents")
        if enabled_connectors:
            parts.append(f"[cyan]{len(enabled_connectors)}[/cyan] connector(s)")

        if parts:
            console.print(f"  [dim]Knowledge: {', '.join(parts)}[/dim]")

        from mneia.config import SOCKET_PATH

        if SOCKET_PATH.exists():
            console.print("  [green]●[/green] [dim]Daemon running[/dim]")
        else:
            console.print("  [dim]●[/dim] [dim]Daemon stopped[/dim]")

        console.print()

    def _handle_command(self, raw: str) -> bool:
        parts = raw.split(None, 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ("/exit", "/quit"):
            console.print("[dim]Goodbye.[/dim]")
            return False

        elif cmd == "/help":
            self._show_help()

        elif cmd == "/clear":
            console.clear()

        elif cmd == "/status":
            self._cmd_status()

        elif cmd == "/stats":
            self._cmd_stats()

        elif cmd == "/search":
            if not args:
                console.print("[yellow]Usage: /search <query>[/yellow]")
            else:
                self._cmd_search(args)

        elif cmd == "/ask":
            if not args:
                console.print("[yellow]Usage: /ask <question>[/yellow]")
            else:
                self._cmd_ask(args)

        elif cmd == "/recent":
            self._cmd_recent()

        elif cmd == "/connectors":
            self._cmd_connectors()

        elif cmd == "/connector-setup":
            if not args:
                self._cmd_connector_setup_interactive()
            else:
                self._cmd_connector_setup(args)

        elif cmd == "/sync":
            if not args:
                console.print("[yellow]Usage: /sync <connector_name>[/yellow]")
            else:
                self._cmd_sync(args)

        elif cmd == "/connector-start":
            if not args:
                self._cmd_connector_start_interactive()
            else:
                self._cmd_connector_start(args)

        elif cmd == "/connector-stop":
            if not args:
                self._cmd_agent_stop_interactive()
            else:
                self._cmd_connector_stop(args)

        elif cmd == "/agents":
            self._cmd_agents()

        elif cmd == "/agent-stats":
            self._cmd_agent_stats()

        elif cmd == "/start":
            if args and args.lower() == "all":
                self._cmd_start_all()
            elif args:
                self._cmd_connector_start(args)
            else:
                self._cmd_start_interactive()

        elif cmd == "/stop":
            if args and args.lower() == "all":
                self._cmd_stop_all()
            elif args:
                self._cmd_connector_stop(args)
            else:
                self._cmd_stop_interactive()

        elif cmd == "/extract":
            limit = int(args) if args.isdigit() else 50
            self._cmd_extract(limit)

        elif cmd == "/graph":
            self._cmd_graph()

        elif cmd == "/graph-entities":
            self._cmd_graph_entities(args if args else None)

        elif cmd == "/graph-person":
            if not args:
                console.print("[yellow]Usage: /graph-person <name>[/yellow]")
            else:
                self._cmd_graph_person(args)

        elif cmd == "/graph-topic":
            if not args:
                console.print("[yellow]Usage: /graph-topic <name>[/yellow]")
            else:
                self._cmd_graph_topic(args)

        elif cmd == "/context":
            self._cmd_context_generate()

        elif cmd == "/config":
            self._cmd_config()

        elif cmd == "/config-llm":
            self._cmd_config_llm()

        elif cmd == "/logs":
            self._cmd_logs(args if args else "info")

        elif cmd == "/chat":
            self._cmd_chat()

        else:
            console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
            console.print("[dim]Type /help for available commands[/dim]")

        return True

    def _show_help(self) -> None:
        table = Table(
            title="[bold]Commands[/bold]",
            show_header=False,
            box=None,
            padding=(0, 2),
        )
        table.add_column("Command", style="cyan", min_width=16)
        table.add_column("Description")

        for cmd, info in SLASH_COMMANDS.items():
            desc = info["desc"]
            if info["alias"]:
                desc += f" [dim](alias: {info['alias']})[/dim]"
            table.add_row(cmd, desc)

        console.print()
        console.print(table)
        console.print()
        if self._ollama_available:
            console.print("[dim]Or just type a question to chat with your knowledge.[/dim]")
        else:
            console.print("[dim]Configure an LLM to ask questions in natural language.[/dim]")
        console.print()

    def _cmd_status(self) -> None:
        from mneia.config import SOCKET_PATH
        from mneia.core.lifecycle import send_command

        if not SOCKET_PATH.exists():
            console.print("[dim]Daemon is not running.[/dim]")
            console.print("[dim]Start with [cyan]/start[/cyan][/dim]")
            return

        try:
            result = asyncio.run(send_command("status"))
            if result.get("running"):
                console.print("[green]● Daemon running[/green]")
                agents = result.get("agents", [])
                if agents:
                    for a in agents:
                        console.print(f"  [cyan]{a['name']}[/cyan] — {a['state']}")
                else:
                    console.print("  [dim]No agents active[/dim]")
            else:
                console.print("[yellow]Daemon not responding.[/yellow]")
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            console.print("[yellow]Daemon not responding.[/yellow]")

    def _cmd_stats(self) -> None:
        from mneia.memory.store import MemoryStore

        store = MemoryStore()
        stats = asyncio.run(store.get_stats())

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="dim")
        table.add_column(style="green", justify="right")

        table.add_row("Documents", str(stats.get("total_documents", 0)))
        table.add_row("Entities", str(stats.get("total_entities", 0)))
        table.add_row("Associations", str(stats.get("total_associations", 0)))

        for source, count in stats.get("by_source", {}).items():
            table.add_row(f"  {source}", str(count))

        console.print(table)

    def _cmd_search(self, query: str) -> None:
        from mneia.memory.store import MemoryStore

        store = MemoryStore()
        results = asyncio.run(store.search(query, limit=5))

        if not results:
            console.print("[dim]No results found.[/dim]")
            return

        for doc in results:
            snippet = doc.content[:300].replace("\n", " ")
            if len(doc.content) > 300:
                snippet += "..."
            console.print(f"\n  [cyan]{doc.title}[/cyan] [dim]({doc.source})[/dim]")
            console.print(f"  [dim]{snippet}[/dim]")

        console.print()

    def _cmd_recent(self) -> None:
        from mneia.memory.store import MemoryStore

        store = MemoryStore()
        results = asyncio.run(store.get_recent(limit=8))

        if not results:
            console.print("[dim]No documents stored yet.[/dim]")
            return

        for doc in results:
            console.print(f"  [cyan]{doc.title[:60]}[/cyan] [dim]{doc.source} · {doc.timestamp[:10]}[/dim]")

    def _cmd_connectors(self) -> None:
        from mneia.connectors import get_available_connectors

        available = get_available_connectors()
        for m in available:
            conn_config = self.config.connectors.get(m.name)
            if conn_config and conn_config.enabled:
                console.print(f"  [green]●[/green] [cyan]{m.name}[/cyan] — {m.display_name}")
            else:
                console.print(f"  [dim]○ {m.name} — {m.display_name}[/dim]")

    def _cmd_sync(self, name: str) -> None:
        conn_config = self.config.connectors.get(name)
        if not conn_config or not conn_config.enabled:
            console.print(f"[yellow]Connector {name} is not enabled.[/yellow]")
            return

        from mneia.connectors import create_connector
        from mneia.pipeline.ingest import ingest_connector

        connector = create_connector(name)
        if not connector:
            console.print(f"[red]Unknown connector: {name}[/red]")
            return

        with console.status(f"[cyan]Syncing {name}...[/cyan]"):
            result = asyncio.run(ingest_connector(connector, conn_config, self.config))

        console.print(f"  [green]Synced {result.documents_ingested} documents from {name}[/green]")

        if conn_config.last_checkpoint != result.checkpoint:
            conn_config.last_checkpoint = result.checkpoint
            self.config.save()

    def _cmd_config(self) -> None:
        console.print(f"  [dim]Provider:[/dim] [cyan]{self.config.llm.provider}[/cyan]")
        console.print(f"  [dim]Model:[/dim] [cyan]{self.config.llm.model}[/cyan]")
        console.print(f"  [dim]Context dir:[/dim] [cyan]{self.config.context_output_dir}[/cyan]")
        enabled = [n for n, c in self.config.connectors.items() if c.enabled]
        console.print(f"  [dim]Connectors:[/dim] [cyan]{', '.join(enabled) or 'none'}[/cyan]")

    def _cmd_start_daemon(self, connectors: list[str] | None = None) -> None:
        import subprocess

        from mneia.config import PID_PATH, SOCKET_PATH

        if SOCKET_PATH.exists():
            console.print("[yellow]Daemon already running.[/yellow]")
            return

        python = sys.executable
        filter_arg = ""
        if connectors is not None:
            filter_arg = f", connector_filter={connectors!r}"
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
        else:
            console.print(
                "[yellow]Daemon starting... "
                "check [cyan]/status[/cyan] in a moment.[/yellow]"
            )

    def _cmd_stop_daemon(self) -> None:
        from mneia.config import PID_PATH
        from mneia.core.lifecycle import send_command

        try:
            asyncio.run(send_command("stop"))
            console.print("[green]● Daemon stopped[/green]")
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            if PID_PATH.exists():
                import os
                import signal as sig

                try:
                    pid = int(PID_PATH.read_text().strip())
                    os.kill(pid, sig.SIGTERM)
                    console.print(f"[green]Sent SIGTERM to PID {pid}.[/green]")
                except (ProcessLookupError, ValueError):
                    console.print("[dim]Stale PID file cleaned up.[/dim]")
                PID_PATH.unlink(missing_ok=True)
            else:
                console.print("[dim]Daemon is not running.[/dim]")

    def _cmd_connector_start(self, name: str) -> None:
        from mneia.core.lifecycle import send_command

        agent_name = f"listener-{name}" if not name.startswith("listener-") else name
        try:
            result = asyncio.run(send_command("start_agent", name=agent_name))
            if result.get("ok"):
                console.print(f"[green]Started agent: {result['started']}[/green]")
            elif result.get("error"):
                console.print(f"[red]{result['error']}[/red]")
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            console.print("[red]Daemon is not running. Use /start first.[/red]")

    def _cmd_connector_stop(self, name: str) -> None:
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

    def _cmd_agents(self) -> None:
        from mneia.core.lifecycle import send_command

        try:
            result = asyncio.run(send_command("list_agents"))
            agents = result.get("agents", [])
            if not agents:
                console.print("[dim]No agents running.[/dim]")
                return
            for a in agents:
                state_icon = "[green]●[/green]" if a["state"] == "running" else "[dim]○[/dim]"
                console.print(f"  {state_icon} [cyan]{a['name']}[/cyan] — {a['state']}")
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            console.print("[dim]Daemon is not running.[/dim]")

    def _cmd_extract(self, limit: int = 50) -> None:
        async def _run() -> None:
            from mneia.core.llm import LLMClient
            from mneia.memory.graph import KnowledgeGraph
            from mneia.memory.store import MemoryStore
            from mneia.pipeline.extract import extract_and_store

            store = MemoryStore()
            graph = KnowledgeGraph()
            llm = LLMClient(self.config.llm)

            try:
                docs = await store.get_unprocessed(limit=limit)
                if not docs:
                    console.print("[dim]No unprocessed documents.[/dim]")
                    return
                console.print(
                    f"[cyan]Extracting from {len(docs)} "
                    f"documents...[/cyan]"
                )
                total_e, total_r = 0, 0
                for i, doc in enumerate(docs, 1):
                    title = doc.title[:50]
                    console.print(
                        f"  [{i}/{len(docs)}] {title}...",
                        end="",
                    )
                    try:
                        result = await extract_and_store(
                            doc, llm, store, graph,
                        )
                        total_e += result["entities"]
                        total_r += result["relationships"]
                        e = result["entities"]
                        r = result["relationships"]
                        console.print(
                            f" [green]OK[/green] {e}E {r}R"
                        )
                    except Exception as e:
                        console.print(f" [red]{e}[/red]")
                console.print(
                    f"\n[green]Extracted {total_e} entities, "
                    f"{total_r} relationships[/green]"
                )
            finally:
                await llm.close()

        asyncio.run(_run())

    def _cmd_graph(self) -> None:
        from mneia.memory.graph import KnowledgeGraph

        graph = KnowledgeGraph()
        stats = graph.get_stats()
        console.print(f"  [dim]Entities:[/dim] [green]{stats['total_nodes']}[/green]")
        console.print(f"  [dim]Relationships:[/dim] [green]{stats['total_edges']}[/green]")
        for etype, count in sorted(stats.get("by_type", {}).items()):
            console.print(f"    [dim]{etype}:[/dim] {count}")

    def _cmd_graph_entities(self, entity_type: str | None = None) -> None:
        from mneia.memory.graph import KnowledgeGraph

        graph = KnowledgeGraph()
        for nid, data in graph._graph.nodes(data=True):
            etype = data.get("entity_type", "unknown")
            if entity_type and etype != entity_type:
                continue
            name = data.get("name", nid)
            desc = data.get("properties", {}).get("description", "")
            console.print(f"  [cyan]{name}[/cyan] [dim]({etype})[/dim] {desc[:60]}")

    @staticmethod
    def _find_graph_node(
        graph: Any, name: str, preferred_type: str | None = None,
    ) -> str | None:
        name_lower = name.lower()
        if preferred_type:
            candidate = f"{preferred_type}:{name_lower.replace(' ', '-')}"
            if candidate in graph._graph:
                return candidate
        for nid, data in graph._graph.nodes(data=True):
            if data.get("name", "").lower() == name_lower:
                return nid
        slug = name_lower.replace(" ", "-")
        for nid in graph._graph.nodes:
            if nid.endswith(f":{slug}"):
                return nid
        for nid, data in graph._graph.nodes(data=True):
            if name_lower in data.get("name", "").lower():
                return nid
        return None

    def _show_graph_entity(self, name: str, preferred_type: str) -> None:
        from mneia.memory.graph import KnowledgeGraph

        graph = KnowledgeGraph()
        node_id = self._find_graph_node(graph, name, preferred_type)
        if not node_id:
            console.print(f"[yellow]No entity found: {name}[/yellow]")
            all_names = []
            for nid, data in graph._graph.nodes(data=True):
                n = data.get("name", "")
                if name.lower() in n.lower():
                    etype = data.get("entity_type", "unknown")
                    all_names.append(f"{n} ({etype})")
            if all_names:
                console.print("[dim]Similar entities:[/dim]")
                for n in all_names[:5]:
                    console.print(f"  [dim]- {n}[/dim]")
            return

        node_data = graph._graph.nodes[node_id]
        display_name = node_data.get("name", name)
        etype = node_data.get("entity_type", "unknown")
        console.print(f"\n  [bold cyan]{display_name}[/bold cyan] [dim]({etype})[/dim]")

        props = node_data.get("properties", {})
        if props.get("description"):
            console.print(f"  [dim]{props['description'][:200]}[/dim]")
        if props.get("source"):
            console.print(f"  [dim]Source: {props['source']}[/dim]")

        result = graph.get_neighbors(node_id, depth=2)
        if result["edges"]:
            for edge in result["edges"]:
                other = edge["target"] if edge["source"] == node_id else edge["source"]
                other_data = graph._graph.nodes.get(other, {})
                fallback = other.split(":", 1)[-1].replace("-", " ").title()
                other_name = other_data.get("name", fallback)
                console.print(f"    [green]{edge['relation']}[/green] → {other_name}")
        else:
            console.print("  [dim]No relationships found.[/dim]")

    def _cmd_graph_person(self, name: str) -> None:
        self._show_graph_entity(name, "person")

    def _cmd_graph_topic(self, name: str) -> None:
        self._show_graph_entity(name, "topic")

    def _cmd_context_generate(self) -> None:
        if not self._ollama_available:
            console.print(
                "[yellow]LLM not configured. "
                "Run /config to set up.[/yellow]"
            )
            return

        output_dir = self.config.context_output_dir
        console.print(
            f"[cyan]Generating context files "
            f"→ [bold]{output_dir}[/bold][/cyan]"
        )

        def on_progress(msg: str) -> None:
            console.print(f"  [dim]{msg}[/dim]")

        async def _run() -> list[str]:
            from mneia.core.llm import LLMClient
            from mneia.memory.graph import KnowledgeGraph
            from mneia.memory.store import MemoryStore
            from mneia.pipeline.generate import generate_context_files

            store = MemoryStore()
            graph = KnowledgeGraph()
            llm = LLMClient(self.config.llm)

            try:
                stats = await store.get_stats()
                total_docs = stats.get("total_documents", 0)
                graph_stats = graph.get_stats()
                total_nodes = graph_stats.get("total_nodes", 0)
                console.print(
                    f"  [dim]{total_docs} documents, "
                    f"{total_nodes} graph nodes[/dim]"
                )
                if total_docs == 0:
                    console.print(
                        "[yellow]No documents ingested yet. "
                        "Sync a connector first.[/yellow]"
                    )
                    return []

                return await generate_context_files(
                    self.config, store, graph, llm,
                    on_progress=on_progress,
                )
            finally:
                await llm.close()

        try:
            generated = asyncio.run(_run())
            if generated:
                for name in generated:
                    path = Path(output_dir) / name
                    console.print(
                        f"  [green]OK[/green] {path}"
                    )
                console.print(
                    f"\n[green]Generated {len(generated)} "
                    f"file(s) in {output_dir}[/green]"
                )
            else:
                console.print(
                    "[yellow]No files generated — "
                    "check templates exist or sync data first.[/yellow]"
                )
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            logger.exception("Context generation failed")

    @staticmethod
    def _build_system_prompt(
        include_commands: bool = False,
        commands_dict: dict[str, Any] | None = None,
    ) -> str:
        local_now = datetime.now()
        date_str = local_now.strftime("%A, %B %d, %Y")
        time_str = local_now.strftime("%H:%M")
        parts = [
            "You are mneia (\u03bc\u03bd\u03b5\u03af\u03b1 — Greek for 'memory'), "
            "a personal knowledge assistant that continuously learns from the user's "
            "digital life. You have access to their calendar events, emails, documents, "
            "notes, audio transcripts, and web research — all ingested from connected "
            "sources and organised into a searchable knowledge base with a knowledge graph "
            "of entities and relationships.\n\n"
            f"Current date and time: {date_str}, {time_str} (local time)\n\n"
            "YOUR ROLE:\n"
            "- Help the user understand, recall, and connect information across their "
            "personal knowledge base.\n"
            "- Answer questions using the provided context from their documents, meetings, "
            "emails, notes, and knowledge graph.\n"
            "- When context is available, always ground your answers in it — reference "
            "specific document titles, people, dates, and sources.\n"
            "- When no relevant context is found, say so honestly and offer to help "
            "in a general capacity.\n"
            "- Be concise, direct, and helpful. Avoid filler.\n"
            "- For time-relative questions ('tomorrow', 'next week', 'yesterday'), "
            "use the current date above to calculate the correct dates.\n"
            "- Suggest 2-3 follow-up questions the user could ask, "
            "prefixed with 'You could also ask:'\n"
            "- If the user's question is ambiguous, ask a clarifying question.",
        ]
        if include_commands and commands_dict:
            cmd_lines = "\n".join(
                f"- {cmd}: {info['desc']}"
                for cmd, info in commands_dict.items()
                if cmd not in ("/help", "/clear", "/exit")
            )
            parts.append(
                "\n\nIf the user's request would be better served by running a "
                "command, include a line starting with COMMAND: followed by the "
                f"slash command.\n\nAvailable commands:\n{cmd_lines}"
            )
        return "\n".join(parts)

    @staticmethod
    def _detect_source_hints(question: str) -> list[str] | None:
        q = question.lower()
        source_keywords: dict[str, list[str]] = {
            "google-calendar": [
                "calendar", "meeting", "meetings", "event", "events",
                "schedule", "appointment", "standup", "sync", "1:1",
                "one-on-one", "invite",
            ],
            "gmail": [
                "email", "emails", "mail", "inbox", "gmail",
                "message", "thread", "sent",
            ],
            "google-drive": [
                "drive", "doc", "docs", "sheet", "sheets",
                "slide", "slides", "google doc",
            ],
            "granola": [
                "meeting", "meeting notes", "transcript",
                "transcription", "conversation", "said",
            ],
        }
        matched = []
        for source, keywords in source_keywords.items():
            if any(kw in q for kw in keywords):
                matched.append(source)
        return matched if matched else None

    def _cmd_ask(self, question: str) -> None:
        if not self._ollama_available:
            console.print(
                "[yellow]LLM not configured. "
                "Run /config to set up.[/yellow]"
            )
            return

        from mneia.core.llm import LLMClient
        from mneia.memory.store import MemoryStore

        async def _run() -> None:
            store = MemoryStore()
            llm = LLMClient(self.config.llm)
            try:
                source_hints = self._detect_source_hints(question)

                results = await store.search(
                    question, limit=5, sources=source_hints,
                )
                if not results and source_hints:
                    results = await store.search(question, limit=5)

                has_context = bool(results)
                source_set: set[str] = set()
                context_parts = []
                for doc in results:
                    source_set.add(doc.source)
                    context_parts.append(
                        f"[{doc.title} \u2014 {doc.source}]\n"
                        f"{doc.content[:1500]}"
                    )

                if has_context:
                    tags = " ".join(
                        self._format_source_tag(s)
                        for s in sorted(source_set)
                    )
                    console.print(
                        f"\n  [green]\u25cf[/green] "
                        f"[dim]Context from:[/dim] {tags} "
                        f"[dim]({len(results)} docs)[/dim]"
                    )
                else:
                    console.print(
                        "\n  [yellow]\u25cb[/yellow] "
                        "[dim]No matching context "
                        "\u2014 answering from general knowledge[/dim]"
                    )

                context_block = (
                    "\n\n---\n\n".join(context_parts)
                    if context_parts
                    else "No relevant documents found."
                )

                system = self._build_system_prompt()
                prompt = (
                    f"Context:\n\n{context_block}\n\n"
                    f"Question: {question}"
                )

                with console.status(
                    "[dim italic]Thinking...[/dim italic]",
                    spinner="dots",
                ):
                    response = await llm.generate(
                        prompt, system=system,
                    )

                console.print()
                border = "green" if has_context else "yellow"
                md = Markdown(response)
                console.print(
                    Panel(md, border_style=border, padding=(1, 2))
                )
                if has_context:
                    console.print("[dim]Sources:[/dim]")
                    for doc in results:
                        tag = self._format_source_tag(doc.source)
                        console.print(
                            f"  [dim]-[/dim] {tag} "
                            f"[dim]{doc.title}[/dim]"
                        )
                console.print()
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
            finally:
                await llm.close()

        try:
            asyncio.run(_run())
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    def _cmd_chat(self) -> None:
        if not self._ollama_available:
            console.print(
                "[yellow]LLM not configured. Run /config to set up.[/yellow]"
            )
            return

        from mneia.conversation import ConversationEngine

        chat_session: PromptSession[str] = PromptSession()
        console.print(
            "[cyan]Chat mode. Type 'exit' to return. "
            "History preserved across turns.[/cyan]\n"
        )

        async def _chat_loop() -> None:
            engine = ConversationEngine(self.config)
            try:
                while True:
                    try:
                        question = chat_session.prompt(
                            HTML("<ansigray>  you ›</ansigray> "),
                        ).strip()
                        if not question:
                            continue
                        if question.lower() in ("exit", "quit", "/exit"):
                            break
                        if question.lower() == "clear":
                            engine.clear_history()
                            console.print(
                                "[dim]  Conversation cleared.[/dim]\n"
                            )
                            continue

                        with console.status(
                            "[dim italic]Thinking...[/dim italic]",
                            spinner="dots",
                        ):
                            result = await engine.ask(question)

                        console.print()
                        md = Markdown(result.answer)
                        console.print(
                            Panel(md, border_style="cyan", padding=(1, 2))
                        )

                        if result.citations:
                            console.print("[dim]  Sources:[/dim]")
                            for cite in result.citations:
                                console.print(
                                    f"    [dim]- {cite.title} "
                                    f"({cite.source})[/dim]"
                                )

                        if result.suggested_followups:
                            console.print(
                                "\n[dim]  You could also ask:[/dim]"
                            )
                            for q in result.suggested_followups:
                                console.print(f"    [cyan]- {q}[/cyan]")
                        console.print()

                    except KeyboardInterrupt:
                        console.print()
                        continue
                    except EOFError:
                        break
            finally:
                await engine.close()
                console.print("[dim]  Back to mneia.[/dim]\n")

        asyncio.run(_chat_loop())

    def _cmd_agent_stats(self) -> None:
        from datetime import datetime

        from mneia.core.agent_stats import AgentStatsDB

        db = AgentStatsDB()
        stats = db.get_stats_24h()

        if not stats:
            console.print("[dim]No agent activity in the last 24 hours.[/dim]")
            db.close()
            return

        for agent_name, events in sorted(stats.items()):
            starts = events.get("start", 0)
            cycles = events.get("cycle", 0)
            errors = events.get("error", 0)
            restarts = events.get("restart", 0)
            error_str = f" [red]{errors} errors[/red]" if errors else ""
            restart_str = f" [yellow]{restarts} restarts[/yellow]" if restarts else ""
            console.print(
                f"  [cyan]{agent_name}[/cyan] — "
                f"{starts} starts, {cycles} cycles{error_str}{restart_str}"
            )

        recent = db.get_recent_events(limit=5)
        if recent:
            console.print("\n  [bold]Recent:[/bold]")
            for ev in recent:
                ts = datetime.fromtimestamp(ev.timestamp).strftime("%H:%M:%S")
                details = f" — {ev.details}" if ev.details else ""
                console.print(f"    [dim]{ts}[/dim] {ev.agent_name}: {ev.event_type}{details}")
        db.close()

    def _cmd_connector_setup_interactive(self) -> None:
        from mneia.connectors import get_available_connectors

        available = get_available_connectors()
        console.print("\n[bold]Available connectors:[/bold]\n")
        for i, m in enumerate(available, 1):
            conn_config = self.config.connectors.get(m.name)
            status = "[green](enabled)[/green]" if conn_config and conn_config.enabled else ""
            console.print(f"  [{i:2d}] [cyan]{m.name:<20}[/cyan] {m.display_name} {status}")

        console.print()
        choice = input("  Choose connector number (or press Enter to cancel): ").strip()
        if not choice or not choice.isdigit():
            return

        idx = int(choice) - 1
        if 0 <= idx < len(available):
            self._cmd_connector_setup(available[idx].name)

    def _cmd_connector_setup(self, name: str) -> None:
        from mneia.config import ConnectorConfig
        from mneia.connectors import MULTI_ACCOUNT_CONNECTORS, create_connector
        from mneia.core.llm_setup import get_connector_help

        account_name = ""
        base_name = name
        if name in MULTI_ACCOUNT_CONNECTORS:
            existing = [
                k for k in self.config.connectors
                if k == name or k.startswith(f"{name}-")
            ]
            if existing:
                console.print(f"\n  [dim]Existing {name} accounts: {', '.join(existing)}[/dim]")
            account_name = input(
                "  Account name (e.g. 'work', 'personal', or Enter for default): "
            ).strip()
            if account_name:
                name = f"{base_name}-{account_name}"

        connector = create_connector(name)
        if not connector:
            console.print(f"[red]Unknown connector: {name}[/red]")
            return

        manifest = connector.manifest
        help_info = get_connector_help(base_name)

        console.print(f"\n  [bold]{manifest.display_name}[/bold]")
        if account_name:
            console.print(f"  [dim]Account: {account_name}[/dim]")
        if help_info:
            console.print(f"  [dim]{help_info['description']}[/dim]\n")
            console.print("  [bold]Prerequisites:[/bold]")
            for line in help_info["prerequisites"].split("\n"):
                console.print(f"    {line}")
            console.print("\n  [bold]What you'll need:[/bold]")
            console.print(f"    {help_info['setup_help']}\n")
        else:
            console.print(f"  [dim]{manifest.description}[/dim]\n")

        if name not in self.config.connectors:
            self.config.connectors[name] = ConnectorConfig(enabled=True)

        if hasattr(connector, "interactive_setup"):
            import inspect
            sig = inspect.signature(connector.interactive_setup)
            if "account" in sig.parameters:
                settings = connector.interactive_setup(account=account_name)
            else:
                settings = connector.interactive_setup()
        else:
            settings = {}

        self.config.connectors[name].settings = settings
        self.config.connectors[name].enabled = True
        self.config.save()

        label = f"{manifest.display_name} ({account_name})" if account_name else manifest.display_name
        console.print(f"\n  [green]{label} configured and enabled![/green]")
        if help_info:
            console.print("\n  [bold]Next steps:[/bold]")
            for line in help_info["next_steps"].split("\n"):
                console.print(f"    {line}")
        else:
            console.print("  Next: [cyan]/start[/cyan] to begin syncing.")
        console.print()

    def _cmd_config_llm(self) -> None:
        from mneia.core.llm_setup import (
            EMBEDDING_MODELS,
            PROVIDER_DISPLAY,
            get_models_for_provider,
        )

        console.print("\n[bold]Choose LLM provider:[/bold]\n")
        providers = list(PROVIDER_DISPLAY.items())
        for i, (key, display) in enumerate(providers, 1):
            current = " [green](current)[/green]" if key == self.config.llm.provider else ""
            console.print(f"  [{i}] {display}{current}")

        choice = input("\n  Provider number: ").strip()
        try:
            provider_key = providers[int(choice) - 1][0]
        except (ValueError, IndexError):
            console.print("[yellow]Cancelled.[/yellow]")
            return

        self.config.llm.provider = provider_key

        if provider_key == "ollama":
            url = input(f"  Ollama URL [{self.config.llm.ollama_base_url}]: ").strip()
            if url:
                self.config.llm.ollama_base_url = url
            models = get_models_for_provider("ollama", self.config.llm.ollama_base_url)
            if models:
                console.print("\n  [bold]Available models:[/bold]")
                for i, m in enumerate(models, 1):
                    current = " [green](current)[/green]" if m == self.config.llm.model else ""
                    console.print(f"    [{i}] {m}{current}")
                mc = input("  Model number or name: ").strip()
                if mc.isdigit() and 1 <= int(mc) <= len(models):
                    self.config.llm.model = models[int(mc) - 1]
                elif mc:
                    self.config.llm.model = mc
            else:
                console.print("  [yellow]Ollama not reachable.[/yellow]")
                mc = input(f"  Model name [{self.config.llm.model}]: ").strip()
                if mc:
                    self.config.llm.model = mc
        else:
            key_fields = {
                "anthropic": ("anthropic_api_key", "Anthropic API key (sk-ant-...)"),
                "openai": ("openai_api_key", "OpenAI API key (sk-...)"),
                "google": ("google_api_key", "Google API key"),
            }
            field, prompt_text = key_fields.get(provider_key, ("", ""))
            if field:
                existing = getattr(self.config.llm, field)
                if existing:
                    console.print(
                        "  [dim]Key set. Press Enter to keep or enter new.[/dim]"
                    )
                import getpass

                key = getpass.getpass(f"  {prompt_text}: ")
                if key:
                    setattr(self.config.llm, field, key)

            api_key = getattr(self.config.llm, field, "") if field else ""
            console.print("  [dim]Fetching available models...[/dim]")
            models = get_models_for_provider(
                provider_key, api_key=api_key or "",
            )
            if models:
                console.print(f"\n  [bold]Available models ({len(models)}):[/bold]")
                for i, m in enumerate(models, 1):
                    console.print(f"    [{i}] {m}")
                mc = input("  Model number or name: ").strip()
                if mc.isdigit() and 1 <= int(mc) <= len(models):
                    self.config.llm.model = models[int(mc) - 1]
                elif mc:
                    self.config.llm.model = mc

            self.config.llm.embedding_model = EMBEDDING_MODELS.get(
                provider_key, self.config.llm.embedding_model,
            )

        self.config.save()
        console.print(
            f"\n  [green]Saved:[/green] [cyan]{self.config.llm.provider}[/cyan] / "
            f"[cyan]{self.config.llm.model}[/cyan]\n"
        )
        self._ollama_available = True

    def _cmd_start_interactive(self) -> None:
        from mneia.config import SOCKET_PATH

        if SOCKET_PATH.exists():
            console.print("  [dim]Daemon is running. Manage connectors:[/dim]\n")
            self._cmd_connector_start_interactive()
            return

        enabled = [
            n for n, c in self.config.connectors.items() if c.enabled
        ]

        console.print("\n  [bold]Start mneia daemon[/bold]\n")
        console.print("  [1] Start with all connectors")
        console.print("  [2] Start core only, then choose connectors")
        console.print()
        choice = input("  Choice: ").strip()

        if choice == "1":
            self._cmd_start_daemon()
        elif choice == "2":
            self._cmd_start_daemon(connectors=[])
            from mneia.config import SOCKET_PATH as SOCK
            if not SOCK.exists():
                return
            if not enabled:
                console.print(
                    "\n  [dim]No connectors enabled. "
                    "Use /connector-setup to enable one.[/dim]"
                )
                return
            console.print()
            self._cmd_connector_start_interactive()
        else:
            console.print("[dim]Cancelled.[/dim]")

    def _cmd_stop_interactive(self) -> None:
        from mneia.config import SOCKET_PATH

        if not SOCKET_PATH.exists():
            console.print("[dim]Daemon is not running.[/dim]")
            return

        from mneia.core.lifecycle import send_command

        try:
            result = asyncio.run(send_command("list_agents"))
            agents = result.get("agents", [])
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            console.print("[dim]Cannot reach daemon.[/dim]")
            return

        connectors = [
            a for a in agents
            if a["state"] == "running" and a["name"].startswith("listener-")
        ]
        core = [
            a for a in agents
            if a["state"] == "running" and not a["name"].startswith("listener-")
        ]

        console.print("\n  [bold]What would you like to stop?[/bold]\n")
        console.print("  [0] Stop daemon (everything)")

        if connectors:
            console.print()
            console.print("  [bold dim]Connectors:[/bold dim]")
            for i, a in enumerate(connectors, 1):
                label = a["name"].replace("listener-", "")
                console.print(f"  [{i}] {label}")

        if core:
            console.print()
            console.print(
                f"  [dim]Core agents running: "
                f"{', '.join(a['name'] for a in core)}[/dim]"
            )

        console.print()
        choice = input("  Choice: ").strip()

        if choice == "0":
            self._cmd_stop_daemon()
        elif choice.isdigit() and 1 <= int(choice) <= len(connectors):
            name = connectors[int(choice) - 1]["name"]
            self._cmd_connector_stop(name)
        else:
            console.print("[dim]Cancelled.[/dim]")

    def _cmd_start_all(self) -> None:
        self._cmd_start_daemon()

    def _cmd_stop_all(self) -> None:
        self._cmd_stop_daemon()

    def _cmd_connector_start_interactive(self) -> None:
        from mneia.config import SOCKET_PATH

        if not SOCKET_PATH.exists():
            console.print("[dim]Daemon not running. Start it first with /start[/dim]")
            return

        enabled = [
            n for n, c in self.config.connectors.items() if c.enabled
        ]
        if not enabled:
            console.print(
                "[dim]No connectors enabled. "
                "Use /connector-setup first.[/dim]"
            )
            return

        from mneia.core.lifecycle import send_command

        try:
            result = asyncio.run(send_command("list_agents"))
            running_names = {
                a["name"] for a in result.get("agents", [])
                if a["state"] == "running"
            }
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            running_names = set()

        not_started = [
            n for n in enabled
            if f"listener-{n}" not in running_names
        ]
        if not not_started:
            console.print("[dim]All connectors are already running.[/dim]")
            return

        console.print("  [bold]Available connectors:[/bold]\n")
        for i, n in enumerate(not_started, 1):
            console.print(f"  [{i}] {n}")
        console.print(f"  [{len(not_started) + 1}] Start all")
        console.print()
        choice = input("  Choice: ").strip()

        if choice.lower() == "a":
            for n in not_started:
                self._cmd_connector_start(n)
        elif choice.isdigit():
            idx = int(choice)
            if idx == len(not_started) + 1:
                for n in not_started:
                    self._cmd_connector_start(n)
            elif 1 <= idx <= len(not_started):
                self._cmd_connector_start(not_started[idx - 1])

    def _cmd_agent_stop_interactive(self) -> None:
        from mneia.core.lifecycle import send_command

        try:
            result = asyncio.run(send_command("list_agents"))
            running = [a for a in result.get("agents", []) if a["state"] == "running"]
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            console.print("[dim]Daemon not running.[/dim]")
            return

        if not running:
            console.print("[dim]No agents running.[/dim]")
            return

        console.print("\n  [bold]Running agents:[/bold]\n")
        for i, a in enumerate(running, 1):
            console.print(f"  [{i}] {a['name']}")
        console.print("  [a] Stop all agents")
        console.print()
        choice = input("  Choice: ").strip()

        if choice.lower() == "a":
            for a in running:
                self._cmd_connector_stop(a["name"])
        elif choice.isdigit() and 1 <= int(choice) <= len(running):
            self._cmd_connector_stop(running[int(choice) - 1]["name"])

    def _cmd_logs(self, level: str = "info") -> None:
        from mneia.config import LOGS_DIR

        log_file = LOGS_DIR / "daemon.log"
        if not log_file.exists():
            console.print("[dim]No log file found.[/dim]")
            return

        level_upper = level.upper()
        level_priority = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "WARN": 2, "ERROR": 3, "CRITICAL": 4}
        min_priority = level_priority.get(level_upper, 1)

        with open(str(log_file)) as f:
            lines = f.readlines()[-30:]
            for line in lines:
                for lname, lprio in level_priority.items():
                    if lname in line.upper() and lprio >= min_priority:
                        console.print(f"  [dim]{line.rstrip()}[/dim]")
                        break
                else:
                    if min_priority <= 1:
                        console.print(f"  [dim]{line.rstrip()}[/dim]")

    def _detect_intent(self, user_input: str) -> tuple[str | None, str]:
        lower = user_input.lower().strip()

        if any(w in lower for w in ["start daemon", "start the daemon", "run daemon", "launch daemon"]):
            return "start", ""
        if any(w in lower for w in ["stop daemon", "stop the daemon", "kill daemon", "shut down"]):
            return "stop", ""
        if any(w in lower for w in ["show stats", "how many documents", "how many notes", "document count"]):
            return "stats", ""
        if any(w in lower for w in ["show recent", "latest documents", "latest notes", "what was ingested"]):
            return "recent", ""
        if any(w in lower for w in ["list connectors", "show connectors", "which connectors", "what connectors"]):
            return "connectors", ""
        if any(w in lower for w in ["show status", "daemon status", "is it running", "are agents running"]):
            return "status", ""
        if lower.startswith("sync "):
            return "sync", lower.split(None, 1)[1] if " " in lower else ""
        if any(w in lower for w in ["show config", "current config", "show settings"]):
            return "config", ""
        if any(w in lower for w in ["show graph", "knowledge graph", "graph stats", "graph summary"]):
            return "graph", ""
        if any(w in lower for w in ["list entities", "show entities", "all entities"]):
            return "graph-entities", ""
        if any(w in lower for w in ["extract entities", "run extraction", "start extraction"]):
            return "extract", ""
        if any(w in lower for w in ["generate context", "create context", "update context files"]):
            return "context", ""
        if any(w in lower for w in ["list agents", "show agents", "running agents", "what agents"]):
            return "agents", ""
        if any(w in lower for w in ["show logs", "daemon logs", "view logs"]):
            return "logs", ""

        import re

        m = re.search(r"(?:start|enable)\s+(?:agent\s+|connector\s+)?(\w+)\s+agent", lower)
        if m:
            return "connector-start", m.group(1)
        m = re.search(r"(?:stop|disable)\s+(?:agent\s+|connector\s+)?(\w+)\s+agent", lower)
        if m:
            return "connector-stop", m.group(1)

        return None, ""

    @staticmethod
    def _format_source_tag(source: str) -> str:
        colors: dict[str, str] = {
            "google-calendar": "bright_green",
            "gmail": "bright_blue",
            "google-drive": "bright_yellow",
            "granola": "bright_magenta",
            "local-folders": "green",
            "obsidian": "bright_cyan",
            "web": "bright_white",
            "knowledge-agent": "bright_red",
            "autonomous-insight": "bright_red",
        }
        color = colors.get(source, "dim")
        if color == "dim":
            for base, c in colors.items():
                if source.startswith(f"{base}-"):
                    color = c
                    break
        return f"[{color}]{source}[/{color}]"

    def _handle_conversation(self, user_input: str) -> None:
        intent, intent_arg = self._detect_intent(user_input)
        if intent:
            console.print(
                f"  [dim]\u2192 Running /{intent} {intent_arg}[/dim]"
            )
            cmd_str = f"/{intent} {intent_arg}".strip()
            self._handle_command(cmd_str)
            return

        if not self._ollama_available:
            console.print("[yellow]LLM not available.[/yellow]")
            console.print(
                "[dim]Run [cyan]/config[/cyan] to set up an LLM[/dim]"
            )
            self._suggest_commands(user_input)
            return

        from mneia.core.llm import LLMClient
        from mneia.memory.store import MemoryStore

        async def _run() -> None:
            store = MemoryStore()
            llm = LLMClient(self.config.llm)
            try:
                source_hints = self._detect_source_hints(user_input)

                search_results = await store.search(
                    user_input, limit=5, sources=source_hints,
                )
                if not search_results and source_hints:
                    search_results = await store.search(
                        user_input, limit=5,
                    )

                has_context = bool(search_results)
                context_parts: list[str] = []
                source_set: set[str] = set()

                if search_results:
                    for doc in search_results:
                        source_set.add(doc.source)
                        context_parts.append(
                            f"[Source: {doc.source}, "
                            f"Title: {doc.title}]\n"
                            f"{doc.content[:1500]}"
                        )

                if has_context:
                    tags = " ".join(
                        self._format_source_tag(s) for s in sorted(source_set)
                    )
                    console.print(
                        f"\n  [green]\u25cf[/green] [dim]Context from:[/dim] "
                        f"{tags} "
                        f"[dim]({len(search_results)} docs)[/dim]"
                    )
                else:
                    console.print(
                        "\n  [yellow]\u25cb[/yellow] "
                        "[dim]No matching context found "
                        "\u2014 answering from general knowledge[/dim]"
                    )

                context_block = (
                    "\n\n---\n\n".join(context_parts)
                    if context_parts
                    else "No relevant documents found."
                )

                system_prompt = self._build_system_prompt(
                    include_commands=True,
                    commands_dict=SLASH_COMMANDS,
                )

                prompt = (
                    f"Context from your knowledge base:\n\n"
                    f"{context_block}\n\n"
                    f"Question: {user_input}"
                )

                thinking = Text(
                    f"  \u2726 {_get_thinking_phrase()}",
                    style="dim italic",
                )
                console.print(thinking)

                response = await llm.generate(
                    prompt, system=system_prompt,
                )

                command_to_run = None
                clean_lines = []
                for line in response.split("\n"):
                    if line.strip().startswith("COMMAND:"):
                        command_to_run = (
                            line.strip().replace("COMMAND:", "").strip()
                        )
                    else:
                        clean_lines.append(line)

                clean_response = "\n".join(clean_lines).strip()

                if clean_response:
                    console.print()
                    border = "green" if has_context else "yellow"
                    md = Markdown(clean_response)
                    console.print(
                        Panel(md, border_style=border, padding=(1, 2))
                    )

                if has_context:
                    console.print("[dim]Sources:[/dim]")
                    for doc in search_results:
                        tag = self._format_source_tag(doc.source)
                        console.print(
                            f"  [dim]-[/dim] {tag} "
                            f"[dim]{doc.title}[/dim]"
                        )
                console.print()

                if command_to_run and command_to_run.startswith("/"):
                    console.print(
                        f"  [dim]\u2192 Running suggested command: "
                        f"[cyan]{command_to_run}[/cyan][/dim]\n"
                    )
                    self._handle_command(command_to_run)

            except Exception as e:
                console.print(f"\n[red]  Error: {e}[/red]")
                console.print(
                    "[dim]  Check your LLM config "
                    "with /config.[/dim]\n"
                )
            finally:
                await llm.close()

        try:
            asyncio.run(_run())
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]\n")

    def _suggest_commands(self, user_input: str) -> None:
        lower = user_input.lower()
        suggestions: list[str] = []

        if any(w in lower for w in ["search", "find", "look"]):
            suggestions.append(f"/search {user_input}")
        if any(w in lower for w in ["recent", "latest", "new"]):
            suggestions.append("/recent")
        if any(w in lower for w in ["stat", "how many", "count"]):
            suggestions.append("/stats")
        if any(w in lower for w in ["status", "running", "daemon"]):
            suggestions.append("/status")
        if any(w in lower for w in ["graph", "entities", "knowledge"]):
            suggestions.append("/graph")
        if any(w in lower for w in ["extract", "process"]):
            suggestions.append("/extract")
        if any(w in lower for w in ["context", "generate"]):
            suggestions.append("/context")
        if any(w in lower for w in ["agent", "agents"]):
            suggestions.append("/agents")

        if suggestions:
            console.print("\n[dim]  Try these commands instead:[/dim]")
            for s in suggestions:
                console.print(f"    [cyan]{s}[/cyan]")
            console.print()


def run_interactive() -> None:
    session = InteractiveSession()
    session.run()
