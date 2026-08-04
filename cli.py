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

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
console = Console()

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
CHROMA_DIR = os.environ.get("CHROMA_DIR", os.path.join(PROJECT_ROOT, "chroma_db"))
COLLECTION_NAME = os.environ.get("CHROMA_COLLECTION", "docs_rag")
RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "4"))
MAX_TOOL_ROUNDS = int(os.environ.get("MAX_TOOL_ROUNDS", "5"))

SYSTEM_PROMPT = (
    "Eres un asistente local que responde preguntas sobre AcmeCloud usando dos "
    "fuentes de informacion:\n\n"
    "1) CONTEXTO RAG: fragmentos de la documentacion indexada (docs/). Usalos "
    "para responder preguntas factuales sobre el producto, su API o su "
    "arquitectura, citando la fuente entre parentesis si la conoces.\n"
    "2) HERRAMIENTAS MCP: usa list_files para inspeccionar carpetas del sistema "
    "y fetch_url para consultar una URL o API publica cuando la pregunta lo "
    "requiera. Para listar el directorio actual de trabajo pasa path='.' o no "
    "pases el argumento. Las rutas son relativas al directorio del proyecto o "
    "rutas Windows absolutas.\n\n"
    "Si el contexto no contiene la respuesta, responde con lo que sepas y no "
    "inventes datos. Responde en espanol.\n\n"
    "=== CONTEXTO RAG ===\n{context}"
)


def retrieve_context(query: str) -> str:
    try:
        import chromadb
        from langchain_community.embeddings import OllamaEmbeddings
    except ImportError:
        return "(RAG no disponible: faltan chromadb/langchain)"
    try:
        client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )
        collection = client.get_collection(COLLECTION_NAME)
    except Exception as exc:
        return f"(RAG no disponible: {exc})"
    embeddings = OllamaEmbeddings(model=OLLAMA_EMBED_MODEL, base_url=OLLAMA_BASE_URL)
    query_vector = embeddings.embed_query(query)
    results = collection.query(query_embeddings=[query_vector], n_results=RAG_TOP_K)
    documents = results.get("documents", [[]])[0] or []
    metadatas = results.get("metadatas", [[]])[0] or []
    blocks = []
    for i, (doc, meta) in enumerate(zip(documents, metadatas), start=1):
        source = (meta or {}).get("source", "?")
        blocks.append(f"--- Fragmento {i} (fuente: {source}) ---\n{doc}")
    return "\n\n".join(blocks) if blocks else "(No se encontraron fragmentos relevantes.)"


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


async def ollama_chat_stream(messages, schemas):
    async with httpx.AsyncClient(timeout=180.0) as client:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": True,
            "options": {"num_ctx": 16384},
        }
        if schemas:
            payload["tools"] = schemas
        async with client.stream(
            "POST", f"{OLLAMA_BASE_URL}/api/chat", json=payload
        ) as response:
            response.raise_for_status()
            content = ""
            tool_calls = []
            async for line in response.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                msg = chunk.get("message", {})
                if msg.get("content"):
                    content += msg["content"]
                if msg.get("tool_calls"):
                    tool_calls = msg["tool_calls"]
            return {"content": content, "tool_calls": tool_calls}


async def run_conversation(session, tools, user_text: str):
    context = retrieve_context(user_text)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
        {"role": "user", "content": user_text},
    ]
    schemas = [mcp_tool_to_schema(tool) for tool in tools]
    tool_log = []

    for _ in range(MAX_TOOL_ROUNDS):
        data = await ollama_chat_stream(messages, schemas)
        content = (data.get("content") or "").strip()
        tool_calls = data.get("tool_calls") or []

        if not tool_calls:
            return content or "(El modelo no devolvio texto.)", tool_log

        messages.append({"role": "assistant", "content": "", "tool_calls": tool_calls})

        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            arguments = fn.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            args_str = json.dumps(arguments, ensure_ascii=False)
            console.print(
                f"  [bold cyan]> MCP[/bold cyan] "
                f"[yellow]{name}[/yellow]({args_str})"
            )
            try:
                result = await session.call_tool(name, arguments)
                result_text = extract_tool_result(result)
            except Exception as exc:
                result_text = f"Error: {exc}"
            tool_log.append({"name": name, "args": arguments})
            messages.append({"role": "tool", "content": result_text})

    return "(No se pudo completar tras varias rondas de herramientas.)", tool_log


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

            console.print()
            console.print("[bold]Herramientas MCP conectadas:[/bold]")
            print_tools(tools)
            console.print()

            if query:
                console.print(f"[bold blue]>[/bold blue] {query}")
                with console.status("[bold cyan]Pensando...[/bold cyan]"):
                    answer, tool_log = await run_conversation(session, tools, query)
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
                    answer, tool_log = await run_conversation(session, tools, user_text)
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
