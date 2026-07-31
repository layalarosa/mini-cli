"""CLI: RAG + herramientas MCP + LLM local (Ollama).

Captura el texto del usuario, recupera contexto de la base RAG (ChromaDB),
conecta las herramientas del servidor MCP al LLM con tool-calling y muestra
la respuesta en pantalla.

Uso:
    python cli.py "que limite de almacenamiento tiene la cuenta gratuita?"
    python cli.py            # modo interactivo
"""

import argparse
import asyncio
import json
import os
import sys

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
CHROMA_DIR = os.environ.get("CHROMA_DIR", os.path.join(PROJECT_ROOT, "chroma_db"))
COLLECTION_NAME = os.environ.get("CHROMA_COLLECTION", "docs_rag")
RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "4"))
MAX_TOOL_ROUNDS = int(os.environ.get("MAX_TOOL_ROUNDS", "5"))

SYSTEM_PROMPT = """Eres un asistente local que responde preguntas sobre AcmeCloud usando dos fuentes de informacion:

1) CONTEXTO RAG: fragmentos de la documentacion indexada (docs/). Usalos para responder preguntas factuales sobre el producto, su API o su arquitectura, citando la fuente entre parentesis si la conoces.
2) HERRAMIENTAS MCP: usa list_files para inspeccionar carpetas del sistema y fetch_url para consultar una URL o API publica cuando la pregunta lo requiera. Para listar el directorio actual de trabajo pasa path='.' o no pases el argumento. Las rutas de archivos son relativas al directorio del proyecto o rutas Windows absolutas.

Si el contexto no contiene la respuesta, responde con lo que sepas y no inventes datos. Responde en espanol.

=== CONTEXTO RAG ===
{context}"""


def retrieve_context(query: str) -> str:
    """Recupera los fragmentos mas relevantes de ChromaDB."""
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
        source = (meta or {}).get("source", "desconocido")
        blocks.append(f"--- Fragmento {i} (fuente: {source}) ---\n{doc}")
    return "\n\n".join(blocks) if blocks else "(No se encontraron fragmentos relevantes.)"


def mcp_tool_to_schema(tool) -> dict:
    """Convierte una herramienta MCP al esquema OpenAI-compatible que usa Ollama."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema or {"type": "object", "properties": {}},
        },
    }


def extract_tool_result(result) -> str:
    parts = []
    for item in result.content:
        text = getattr(item, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts) if parts else "(sin contenido)"


async def ollama_chat(messages, schemas) -> dict:
    async with httpx.AsyncClient(timeout=180.0) as client:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"num_ctx": 16384},
        }
        if schemas:
            payload["tools"] = schemas
        response = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        response.raise_for_status()
        return response.json()


async def run_conversation(session, tools, user_text: str) -> str:
    context = retrieve_context(user_text)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
        {"role": "user", "content": user_text},
    ]
    schemas = [mcp_tool_to_schema(tool) for tool in tools]

    for _ in range(MAX_TOOL_ROUNDS):
        data = await ollama_chat(messages, schemas)
        message = data.get("message", {})
        content = (message.get("content") or "").strip()
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            return content or "(El modelo no devolvio texto.)"

        messages.append({"role": "assistant", "content": "", "tool_calls": tool_calls})

        for tool_call in tool_calls:
            fn = tool_call.get("function", {})
            name = fn.get("name", "")
            arguments = fn.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            print(f"  [MCP] {name}({json.dumps(arguments, ensure_ascii=False)})")
            try:
                result = await session.call_tool(name, arguments)
                result_text = extract_tool_result(result)
            except Exception as exc:
                result_text = f"Error al ejecutar la herramienta {name}: {exc}"
            messages.append({"role": "tool", "content": result_text})

    return "(Lo siento, no pude completar la respuesta tras varias rondas de herramientas.)"


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
            print("Herramientas MCP conectadas:")
            for tool in tools:
                desc = (tool.description or "").splitlines()[0] if tool.description else ""
                print(f"  - {tool.name}: {desc}")

            if query:
                print(f"\n> {query}")
                answer = await run_conversation(session, tools, query)
                print(f"\n{answer}\n")
                return

            print("\nChat RAG + MCP local. Escribe tu pregunta o 'salir' para terminar.\n")
            while True:
                try:
                    user_text = input("Tu> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nHasta luego.")
                    break
                if not user_text:
                    continue
                if user_text.lower() in ("salir", "exit", "/quit"):
                    break
                print("...")
                answer = await run_conversation(session, tools, user_text)
                print(f"\n{answer}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI RAG + MCP + Ollama.")
    parser.add_argument("query", nargs="*", help="Pregunta (si se omite, modo interactivo)")
    args = parser.parse_args()

    query = " ".join(args.query).strip() or None
    try:
        asyncio.run(amain(query))
    except KeyboardInterrupt:
        print("\nInterrumpido.")
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
