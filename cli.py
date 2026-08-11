"""CLI de AcmeCloud: RAG + herramientas MCP + Ollama local."""

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

from app.assistant_service import answer_query, retrieve_context

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
console = Console()


def mcp_tool_to_schema(tool) -> dict:
    return {"type": "function", "function": {"name": tool.name, "description": tool.description or "", "parameters": tool.inputSchema or {"type": "object", "properties": {}}}}


def extract_tool_result(result) -> str:
    parts = [getattr(item, "text", None) or "" for item in result.content]
    return "\n".join(part for part in parts if part) or "(sin contenido)"


def print_answer(answer: str, tool_log: list[dict] | None = None) -> None:
    if tool_log:
        table = Table(show_header=True, header_style="bold cyan", padding=(0, 1))
        table.add_column("Herramienta", style="yellow", no_wrap=True)
        table.add_column("Argumentos")
        for call in tool_log:
            table.add_row(call["name"], json.dumps(call["args"], ensure_ascii=False))
        console.print(table)
    console.print(Panel(Markdown(answer), title="[bold green]Respuesta[/bold green]", border_style="green", padding=(1, 2)))


def print_tools(tools) -> None:
    table = Table(show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("Herramienta", style="yellow", no_wrap=True)
    table.add_column("Descripción")
    for tool in tools:
        table.add_row(tool.name, (tool.description or "").splitlines()[0])
    console.print(table)


async def list_mcp_tools() -> None:
    server_params = StdioServerParameters(command=sys.executable, args=[os.path.join(PROJECT_ROOT, "mcp_server.py")], cwd=PROJECT_ROOT)
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print_tools((await session.list_tools()).tools)


async def answer_with_mcp(query: str) -> None:
    server_params = StdioServerParameters(command=sys.executable, args=[os.path.join(PROJECT_ROOT, "mcp_server.py")], cwd=PROJECT_ROOT)
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools

            async def call_mcp_tool(name: str, arguments: dict) -> str:
                console.print(f"  [bold cyan]> MCP[/bold cyan] [yellow]{name}[/yellow]({json.dumps(arguments, ensure_ascii=False)})")
                try:
                    return extract_tool_result(await session.call_tool(name, arguments))
                except Exception as exc:
                    return f"Error: {exc}"

            with console.status("[bold cyan]Consultando...[/bold cyan]"):
                answer, tool_log = await answer_query(query, [mcp_tool_to_schema(tool) for tool in tools], call_mcp_tool)
            print_answer(answer, tool_log)


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI local: RAG + MCP + Ollama.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    ask_parser = subcommands.add_parser("ask", help="Responde una consulta usando RAG, Ollama y MCP")
    ask_parser.add_argument("query", nargs="+", help="Consulta que se enviará al asistente")
    rag_parser = subcommands.add_parser("rag", help="Muestra el contexto RAG sin usar el LLM")
    rag_parser.add_argument("query", nargs="+", help="Consulta para buscar en la base documental")
    subcommands.add_parser("tools", help="Lista las herramientas MCP disponibles")
    args = parser.parse_args()
    try:
        if args.command == "ask":
            asyncio.run(answer_with_mcp(" ".join(args.query)))
        elif args.command == "rag":
            console.print(Panel(retrieve_context(" ".join(args.query)), title="Contexto RAG", border_style="dim"))
        else:
            asyncio.run(list_mcp_tools())
    except KeyboardInterrupt:
        console.print("\n[dim]Interrumpido.[/dim]")
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
