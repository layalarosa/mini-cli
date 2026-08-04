"""Web local: interfaz de chat con Streamlit.

Ejecuta:
    streamlit run streamlit_app.py
"""

import json
import os
import sys

import httpx
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import (
    OLLAMA_BASE_URL,
    OLLAMA_EMBED_MODEL,
    OLLAMA_MODEL,
    CHROMA_DIR,
    COLLECTION_NAME,
    MAX_TOOL_ROUNDS,
    RAG_TOP_K,
    SYSTEM_PROMPT,
    retrieve_context,
)
from mcp_server import fetch_url, list_files

TOOL_FUNCTIONS = {"list_files": list_files, "fetch_url": fetch_url}

st.set_page_config(page_title="Mini-CLI RAG+MCP", page_icon=":brain:", layout="centered")
st.title("Mini-CLI: RAG + MCP + Ollama")
st.caption("Asistente local con base RAG y herramientas MCP")

with st.sidebar:
    st.header("Configuracion")
    st.markdown(
        f"**LLM:** `{OLLAMA_MODEL}`\n"
        f"**Embeddings:** `{OLLAMA_EMBED_MODEL}`\n"
        f"**RAG top_k:** {RAG_TOP_K}\n"
        f"**Max rondas tool:** {MAX_TOOL_ROUNDS}"
    )
    st.header("Herramientas MCP")
    st.markdown(
        "- **list_files**: lista archivos de un directorio\n"
        "- **fetch_url**: hace GET a una URL/API"
    )
    if st.button("Reconstruir RAG"):
        with st.spinner("Indexando documentos..."):
            from rag_build import build_index
            build_index("./docs", CHROMA_DIR, COLLECTION_NAME)
        st.success("Indice actualizado.")


def call_tool(name: str, arguments: dict) -> str:
    fn = TOOL_FUNCTIONS.get(name)
    if not fn:
        return f"Herramienta desconocida: {name}"
    try:
        return fn(**arguments)
    except Exception as exc:
        return f"Error: {exc}"


def ollama_chat_sync(messages, schemas):
    with httpx.Client(timeout=180.0) as client:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"num_ctx": 16384},
        }
        if schemas:
            payload["tools"] = schemas
        resp = client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json()


def get_response(user_text: str):
    context = retrieve_context(user_text)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
        {"role": "user", "content": user_text},
    ]
    schemas = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["desc"],
                "parameters": t["schema"],
            },
        }
        for t in [
            {
                "name": "list_files",
                "desc": "Lista archivos de un directorio local.",
                "schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "default": ".",
                            "description": "Directorio a listar",
                        }
                    },
                },
            },
            {
                "name": "fetch_url",
                "desc": "GET a una URL y devuelve status + contenido.",
                "schema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL a consultar"},
                        "max_chars": {
                            "type": "integer",
                            "default": 2000,
                        },
                    },
                    "required": ["url"],
                },
            },
        ]
    ]
    tool_log = []

    for _ in range(MAX_TOOL_ROUNDS):
        data = ollama_chat_sync(messages, schemas)
        msg = data.get("message", {})
        content = (msg.get("content") or "").strip()
        tool_calls = msg.get("tool_calls") or []

        if not tool_calls:
            return content or "(Sin respuesta)", tool_log

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
            result_text = call_tool(name, arguments)
            tool_log.append({"name": name, "args": arguments, "result": result_text})
            messages.append({"role": "tool", "content": result_text})

    return "(Maximo de rondas alcanzado.)", tool_log


if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                with st.expander(f":wrench: {tc['name']}({json.dumps(tc['args'], ensure_ascii=False)})"):
                    st.code(tc["result"], language=None)
        st.markdown(msg["content"])

if user_text := st.chat_input("Escribe tu pregunta..."):
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)

    with st.spinner("Pensando..."):
        answer, tool_log = get_response(user_text)

    with st.chat_message("assistant"):
        if tool_log:
            for tc in tool_log:
                with st.expander(f":wrench: {tc['name']}({json.dumps(tc['args'], ensure_ascii=False)})"):
                    st.code(tc["result"], language=None)
        st.markdown(answer)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "tool_calls": tool_log if tool_log else None,
    })
