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
    "/ask": {"desc": "Ask a question with RAG — /ask <question>", "alias": ""},
    "/stats": {"desc": "Show memory statistics", "alias": ""},
    "/recent": {"desc": "Show recently ingested documents", "alias": ""},
    "/connectors": {"desc": "List connectors and their status", "alias": ""},
    "/sync": {"desc": "Sync a connector — /sync <name>", "alias": ""},
    "/connector-start": {"desc": "Start a connector agent — /connector-start <name>", "alias": ""},
    "/connector-stop": {"desc": "Stop a connector agent — /connector-stop <name>", "alias": ""},
    "/agents": {"desc": "List running agents", "alias": ""},
    "/extract": {"desc": "Run entity extraction — /extract [limit]", "alias": ""},
    "/graph": {"desc": "Show knowledge graph summary", "alias": ""},
    "/graph-entities": {"desc": "List entities — /graph-entities [type]", "alias": ""},
    "/graph-person": {"desc": "Show person info — /graph-person <name>", "alias": ""},
    "/graph-topic": {"desc": "Show topic info — /graph-topic <name>", "alias": ""},
    "/context": {"desc": "Generate context .md files", "alias": ""},
    "/config": {"desc": "Show current configuration", "alias": ""},
    "/start": {"desc": "Start the daemon (background)", "alias": ""},
    "/stop": {"desc": "Stop the daemon", "alias": ""},
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

        elif cmd == "/ask":
            if not args:
                console.print("[yellow]Usage: /ask <question>[/yellow]")
            else:
                self._cmd_ask(args)

        elif cmd == "/recent":
            self._cmd_recent()

        elif cmd == "/connectors":
            self._cmd_connectors()

        elif cmd == "/sync":
            if not args:
                console.print("[yellow]Usage: /sync <connector_name>[/yellow]")
            else:
                self._cmd_sync(args)

        elif cmd == "/connector-start":
            if not args:
                console.print("[yellow]Usage: /connector-start <name>[/yellow]")
            else:
                self._cmd_connector_start(args)

        elif cmd == "/connector-stop":
            if not args:
                console.print("[yellow]Usage: /connector-stop <name>[/yellow]")
            else:
                self._cmd_connector_stop(args)

        elif cmd == "/agents":
            self._cmd_agents()

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

        elif cmd == "/start":
            self._cmd_start_daemon()

        elif cmd == "/stop":
            self._cmd_stop_daemon()

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
        from mneia.core.llm import LLMClient
        from mneia.memory.graph import KnowledgeGraph
        from mneia.memory.store import MemoryStore
        from mneia.pipeline.extract import extract_and_store

        store = MemoryStore()
        graph = KnowledgeGraph()
        llm = LLMClient(self.config.llm)

        async def _run() -> None:
            docs = await store.get_unprocessed(limit=limit)
            if not docs:
                console.print("[dim]No unprocessed documents.[/dim]")
                return
            console.print(f"[cyan]Extracting from {len(docs)} documents...[/cyan]")
            total_e, total_r = 0, 0
            for i, doc in enumerate(docs, 1):
                console.print(f"  [{i}/{len(docs)}] {doc.title[:50]}...", end="")
                try:
                    result = await extract_and_store(doc, llm, store, graph)
                    total_e += result["entities"]
                    total_r += result["relationships"]
                    console.print(f" [green]OK[/green] {result['entities']}E {result['relationships']}R")
                except Exception as e:
                    console.print(f" [red]{e}[/red]")
            console.print(f"\n[green]Extracted {total_e} entities, {total_r} relationships[/green]")

        try:
            asyncio.run(_run())
        finally:
            asyncio.run(llm.close())

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

    def _cmd_graph_person(self, name: str) -> None:
        from mneia.memory.graph import KnowledgeGraph

        graph = KnowledgeGraph()
        node_id = f"person:{name.lower().replace(' ', '-')}"
        result = graph.get_neighbors(node_id, depth=2)
        if not result["nodes"]:
            console.print(f"[yellow]No person found: {name}[/yellow]")
            return
        console.print(f"\n  [bold cyan]{name}[/bold cyan]")
        for edge in result["edges"]:
            other = edge["target"] if edge["source"] == node_id else edge["source"]
            other_name = other.split(":", 1)[-1].replace("-", " ").title()
            console.print(f"    [green]{edge['relation']}[/green] → {other_name}")

    def _cmd_graph_topic(self, name: str) -> None:
        from mneia.memory.graph import KnowledgeGraph

        graph = KnowledgeGraph()
        node_id = f"topic:{name.lower().replace(' ', '-')}"
        result = graph.get_neighbors(node_id, depth=2)
        if not result["nodes"]:
            console.print(f"[yellow]No topic found: {name}[/yellow]")
            return
        console.print(f"\n  [bold cyan]{name}[/bold cyan]")
        for edge in result["edges"]:
            other = edge["target"] if edge["source"] == node_id else edge["source"]
            other_name = other.split(":", 1)[-1].replace("-", " ").title()
            console.print(f"    [green]{edge['relation']}[/green] → {other_name}")

    def _cmd_context_generate(self) -> None:
        from mneia.core.llm import LLMClient
        from mneia.memory.graph import KnowledgeGraph
        from mneia.memory.store import MemoryStore
        from mneia.pipeline.generate import generate_context_files

        store = MemoryStore()
        graph = KnowledgeGraph()
        llm = LLMClient(self.config.llm)

        console.print("[cyan]Generating context files...[/cyan]")
        try:
            generated = asyncio.run(generate_context_files(self.config, store, graph, llm))
            if generated:
                for name in generated:
                    console.print(f"  [green]OK[/green] {name}")
                console.print(f"\n[green]Generated {len(generated)} file(s)[/green]")
            else:
                console.print("[yellow]No files generated.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        finally:
            asyncio.run(llm.close())

    def _cmd_ask(self, question: str) -> None:
        if not self._ollama_available:
            console.print("[yellow]LLM not available. Start Ollama or configure an API key.[/yellow]")
            return

        from mneia.core.llm import LLMClient
        from mneia.memory.store import MemoryStore

        store = MemoryStore()
        results = asyncio.run(store.search(question, limit=5))

        context_parts = []
        for doc in results:
            context_parts.append(f"[{doc.title} — {doc.source}]\n{doc.content[:1500]}")

        context_block = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant documents found."

        system = (
            "You are mneia, a personal knowledge assistant. "
            "Answer based on the provided context from the user's documents. "
            "Be concise, direct, and helpful. Reference specific documents when possible."
        )
        prompt = f"Context:\n\n{context_block}\n\nQuestion: {question}"

        llm = LLMClient(self.config.llm)
        try:
            response = asyncio.run(llm.generate(prompt, system=system))
            console.print()
            md = Markdown(response)
            console.print(Panel(md, border_style="cyan", padding=(1, 2)))
            if results:
                console.print("[dim]Sources:[/dim]")
                for doc in results:
                    console.print(f"  [dim]- {doc.title} ({doc.source})[/dim]")
            console.print()
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        finally:
            asyncio.run(llm.close())

    def _cmd_chat(self) -> None:
        if not self._ollama_available:
            console.print("[yellow]LLM not available. Start Ollama or configure an API key.[/yellow]")
            return

        from mneia.conversation import ConversationEngine

        engine = ConversationEngine(self.config)
        console.print("[cyan]Chat mode. Type 'exit' to return. History preserved across turns.[/cyan]\n")

        try:
            while True:
                try:
                    question = input("  you › ").strip()
                    if not question:
                        continue
                    if question.lower() in ("exit", "quit", "/exit"):
                        break
                    if question.lower() == "clear":
                        engine.clear_history()
                        console.print("[dim]  Conversation cleared.[/dim]\n")
                        continue

                    with console.status("[dim italic]Thinking...[/dim italic]", spinner="dots"):
                        result = asyncio.run(engine.ask(question))

                    console.print()
                    md = Markdown(result.answer)
                    console.print(Panel(md, border_style="cyan", padding=(1, 2)))

                    if result.citations:
                        console.print("[dim]  Sources:[/dim]")
                        for cite in result.citations:
                            console.print(f"    [dim]- {cite.title} ({cite.source})[/dim]")

                    if result.suggested_followups:
                        console.print("\n[dim]  You could also ask:[/dim]")
                        for q in result.suggested_followups:
                            console.print(f"    [cyan]- {q}[/cyan]")
                    console.print()

                except KeyboardInterrupt:
                    console.print()
                    continue
                except EOFError:
                    break
        finally:
            asyncio.run(engine.close())
            console.print("[dim]  Back to mneia.[/dim]\n")

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

    def _handle_conversation(self, user_input: str) -> None:
        intent, intent_arg = self._detect_intent(user_input)
        if intent:
            console.print(f"  [dim]→ Running /{intent} {intent_arg}[/dim]")
            cmd_str = f"/{intent} {intent_arg}".strip()
            self._handle_command(cmd_str)
            return

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

        available_commands = "\n".join(
            f"- {cmd}: {info['desc']}" for cmd, info in SLASH_COMMANDS.items()
            if cmd not in ("/help", "/clear", "/exit")
        )

        system_prompt = (
            "You are mneia, a personal knowledge assistant. "
            "You help the user understand their own knowledge, notes, meetings, and work. "
            "Answer based on the provided context from the user's documents. "
            "Be concise, direct, and helpful. "
            "If the context doesn't contain relevant information, say so honestly. "
            "Reference specific documents when possible.\n\n"
            "If the user's question is too vague to answer well, ask a clarifying question. "
            "Suggest specific follow-ups the user could ask.\n\n"
            "IMPORTANT: If the user's request would be better served by running a command, "
            "include a line starting with COMMAND: followed by the slash command. For example:\n"
            "COMMAND: /search meeting notes\n"
            "COMMAND: /graph\n"
            "COMMAND: /extract\n\n"
            f"Available commands:\n{available_commands}"
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

            command_to_run = None
            clean_lines = []
            for line in response.split("\n"):
                if line.strip().startswith("COMMAND:"):
                    command_to_run = line.strip().replace("COMMAND:", "").strip()
                else:
                    clean_lines.append(line)

            clean_response = "\n".join(clean_lines).strip()

            if clean_response:
                console.print()
                md = Markdown(clean_response)
                console.print(Panel(md, border_style="cyan", padding=(1, 2)))
                console.print()

            if command_to_run and command_to_run.startswith("/"):
                console.print(f"  [dim]→ Running suggested command: [cyan]{command_to_run}[/cyan][/dim]\n")
                self._handle_command(command_to_run)

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
