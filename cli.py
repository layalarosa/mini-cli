"""CLI mejorado: RAG + herramientas MCP + LLM local (Ollama).

Comandos interactivos:
    /help      Ayuda
    /tools     Lista herramientas MCP
    /rag q     Busca en la base RAG sin LLM
    /quit      Salir
"""

import argparse
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from app.chat_service import retrieve_context, run_conversation as shared_run_conversation

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
console = Console()

def mcp_tool_to_schema(tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema or {"type": "object", "properties": {}},
        },
    }


def extract_tool_result(result) -> str:
    parts = [getattr(item, "text", None) or "" for item in result.content]
    return "\n".join(p for p in parts if p) or "(sin contenido)"


def print_answer(answer: str, tool_log=None) -> None:
    if tool_log:
        table = Table(show_header=True, header_style="bold cyan", padding=(0, 1))
        table.add_column("Herramienta", style="yellow", no_wrap=True)
        table.add_column("Argumentos")
        for t in tool_log:
            table.add_row(t["name"], json.dumps(t["args"], ensure_ascii=False))
        console.print(table)
    try:
        content = Markdown(answer)
    except Exception:
        content = answer
    console.print(Panel(content, title="[bold green]Respuesta[/bold green]", border_style="green", padding=(1, 2)))


def print_tools(tools) -> None:
    table = Table(show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("Herramienta", style="yellow", no_wrap=True)
    table.add_column("Descripcion")
    for tool in tools:
        desc = (tool.description or "").splitlines()[0] if tool.description else ""
        table.add_row(tool.name, desc)
    console.print(table)


async def amain(query: str | None) -> None:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(PROJECT_ROOT, "mcp_server.py")],
        cwd=PROJECT_ROOT,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            schemas = [mcp_tool_to_schema(tool) for tool in tools]

            async def call_mcp_tool(name: str, arguments: dict) -> str:
                console.print(f"  [bold cyan]> MCP[/bold cyan] [yellow]{name}[/yellow]({json.dumps(arguments, ensure_ascii=False)})")
                try:
                    return extract_tool_result(await session.call_tool(name, arguments))
                except Exception as exc:
                    return f"Error: {exc}"

            console.print()
            console.print("[bold]Herramientas MCP conectadas:[/bold]")
            print_tools(tools)
            console.print()

            if query:
                console.print(f"[bold blue]>[/bold blue] {query}")
                with console.status("[bold cyan]Pensando...[/bold cyan]"):
                    answer, tool_log = await shared_run_conversation(query, schemas, call_mcp_tool)
                print_answer(answer, tool_log)
                return

            console.print("[bold]Mini-CLI[/bold] [dim]RAG + MCP + Ollama local[/dim]")
            console.print("[dim]Escribe tu pregunta, /help para ayuda, o 'salir' para terminar.[/dim]\n")

            while True:
                try:
                    user_text = input("Tu> ").strip()
                except (EOFError, KeyboardInterrupt):
                    console.print("\n[dim]Hasta luego.[/dim]")
                    break
                if not user_text:
                    continue
                if user_text.lower() in ("salir", "exit", "/quit"):
                    break
                if user_text in ("/help", "/?"):
                    console.print(Panel(
                        "[bold]/help[/bold]    Muestra esta ayuda\n"
                        "[bold]/tools[/bold]   Lista herramientas MCP\n"
                        "[bold]/rag[/bold] q    Busca en la base RAG sin LLM\n"
                        "[bold]/quit[/bold]     Salir",
                        title="Comandos", border_style="dim",
                    ))
                    continue
                if user_text == "/tools":
                    print_tools(tools)
                    continue
                if user_text.startswith("/rag "):
                    ctx = retrieve_context(user_text[5:])
                    console.print(Panel(ctx, title="Contexto RAG", border_style="dim"))
                    continue

                with console.status("[bold cyan]Pensando...[/bold cyan]"):
                    answer, tool_log = await shared_run_conversation(user_text, schemas, call_mcp_tool)
                print_answer(answer, tool_log)


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI mejorado: RAG + MCP + Ollama.")
    parser.add_argument("query", nargs="*", help="Pregunta (si se omite, modo interactivo)")
    args = parser.parse_args()
    query = " ".join(args.query).strip() or None
    try:
        asyncio.run(amain(query))
    except KeyboardInterrupt:
        console.print("\n[dim]Interrumpido.[/dim]")
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
