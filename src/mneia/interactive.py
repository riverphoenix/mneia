from __future__ import annotations

import asyncio
import shutil
import sys
import time
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from mneia import __version__
from mneia.config import MNEIA_DIR, MneiaConfig, ensure_dirs

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
    "/stats": {"desc": "Show memory statistics", "alias": ""},
    "/recent": {"desc": "Show recently ingested documents", "alias": ""},
    "/connectors": {"desc": "List connectors and their status", "alias": ""},
    "/sync": {"desc": "Sync a connector — /sync <name>", "alias": ""},
    "/config": {"desc": "Show current configuration", "alias": ""},
    "/start": {"desc": "Start the daemon (background)", "alias": ""},
    "/stop": {"desc": "Stop the daemon", "alias": ""},
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
        self._completer = WordCompleter(
            list(SLASH_COMMANDS.keys()) + ["/quit"],
            sentence=True,
        )

    def run(self) -> None:
        console.print(BANNER)
        console.print(f"  [dim]v{__version__} — your personal knowledge agent[/dim]")
        console.print(f"  [dim]Type [cyan]/help[/cyan] for commands or just ask a question.[/dim]\n")

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

    def _check_ollama_status(self) -> None:
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
            console.print("  [red]●[/red] [dim]Ollama not running — conversational mode unavailable[/dim]")
            console.print("    [dim]To enable, install and start Ollama:[/dim]")
            console.print("    [dim]  brew install ollama[/dim]")
            console.print("    [dim]  ollama serve[/dim]")
            console.print(f"    [dim]  ollama pull {self.config.llm.model}[/dim]")

        if self.config.llm.provider != "ollama" and (
            self.config.llm.anthropic_api_key or self.config.llm.openai_api_key
        ):
            self._ollama_available = True
            console.print(
                f"  [green]●[/green] [dim]LLM ready ([cyan]{self.config.llm.model}[/cyan] via {self.config.llm.provider})[/dim]"
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

        elif cmd == "/recent":
            self._cmd_recent()

        elif cmd == "/connectors":
            self._cmd_connectors()

        elif cmd == "/sync":
            if not args:
                console.print("[yellow]Usage: /sync <connector_name>[/yellow]")
            else:
                self._cmd_sync(args)

        elif cmd == "/config":
            self._cmd_config()

        elif cmd == "/start":
            self._cmd_start_daemon()

        elif cmd == "/stop":
            self._cmd_stop_daemon()

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
            console.print("[dim]Enable Ollama to ask questions in natural language.[/dim]")
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

    def _cmd_start_daemon(self) -> None:
        import os
        import subprocess

        from mneia.config import SOCKET_PATH

        if SOCKET_PATH.exists():
            console.print("[yellow]Daemon already running.[/yellow]")
            return

        python = sys.executable
        cmd = [
            python, "-c",
            "import asyncio; from mneia.config import MneiaConfig; "
            "from mneia.core.lifecycle import AgentManager; "
            "config = MneiaConfig.load(); "
            "manager = AgentManager(config); "
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
            console.print(f"[green]● Daemon started[/green] [dim](PID {proc.pid})[/dim]")
            console.print(f"  [dim]Logs: {log_path}[/dim]")
            console.print(f"  [dim]Stop with [cyan]/stop[/cyan][/dim]")
        else:
            console.print("[yellow]Daemon starting... check [cyan]/status[/cyan] in a moment.[/yellow]")

    def _cmd_stop_daemon(self) -> None:
        from mneia.core.lifecycle import send_command

        try:
            asyncio.run(send_command("stop"))
            console.print("[green]● Daemon stopped[/green]")
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            console.print("[dim]Daemon is not running.[/dim]")

    def _handle_conversation(self, user_input: str) -> None:
        if not self._ollama_available:
            console.print("[yellow]LLM not available.[/yellow]")
            console.print("[dim]Start Ollama or configure an API key in [cyan]/config[/cyan][/dim]")
            self._suggest_commands(user_input)
            return

        from mneia.core.llm import LLMClient
        from mneia.memory.store import MemoryStore

        store = MemoryStore()

        with console.status(f"[dim italic]{_get_thinking_phrase()}[/dim italic]", spinner="dots"):
            search_results = asyncio.run(store.search(user_input, limit=5))

        context_parts: list[str] = []
        if search_results:
            console.print(f"  [dim]Found {len(search_results)} relevant documents[/dim]")
            for doc in search_results:
                context_parts.append(
                    f"[Source: {doc.source}, Title: {doc.title}]\n{doc.content[:1500]}"
                )

        context_block = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant documents found."

        system_prompt = (
            "You are mneia, a personal knowledge assistant. "
            "You help the user understand their own knowledge, notes, meetings, and work. "
            "Answer based on the provided context from the user's documents. "
            "Be concise, direct, and helpful. "
            "If the context doesn't contain relevant information, say so honestly. "
            "Reference specific documents when possible."
        )

        prompt = f"""Context from your knowledge base:

{context_block}

Question: {user_input}"""

        llm = LLMClient(self.config.llm)

        console.print()
        thinking_text = Text(f"  ✦ {_get_thinking_phrase()}", style="dim italic")
        console.print(thinking_text)

        try:
            response = asyncio.run(llm.generate(prompt, system=system_prompt))
            console.print()
            md = Markdown(response)
            console.print(Panel(md, border_style="cyan", padding=(1, 2)))
            console.print()
        except Exception as e:
            console.print(f"\n[red]  Error: {e}[/red]")
            console.print("[dim]  Check that Ollama is running and the model is available.[/dim]\n")
        finally:
            asyncio.run(llm.close())

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

        if suggestions:
            console.print("\n[dim]  Try these commands instead:[/dim]")
            for s in suggestions:
                console.print(f"    [cyan]{s}[/cyan]")
            console.print()


def run_interactive() -> None:
    session = InteractiveSession()
    session.run()
