# mini-cli: CLI con RAG + herramientas MCP + LLM local

Asistente de linea de comandos que une tres piezas:

1. **Servidor MCP** (`mcp_server.py`): expone herramientas locales mediante el
   protocolo MCP (stdlib).
2. **Base RAG** (`rag_build.py`): indexa los `.md` de `docs/` en ChromaDB
   usando LangChain para la carga y division de documentos y embeddings
   generados con Ollama (`nomic-embed-text`).
3. **CLI** (`cli.py`): captura el texto del usuario, recupera contexto del RAG,
   le entrega al LLM las herramientas MCP (tool-calling) y muestra la respuesta
   en pantalla.

## Requisitos

- Python 3.10+
- [Ollama](https://ollama.com) en ejecucion con los modelos:
  - `ollama pull llama3.1:8b` (LLM con soporte de tools)
  - `ollama pull nomic-embed-text` (embeddings para el RAG)

## Instalacion

```powershell
git clone https://github.com/layalarosa/mini-cli.git
cd mini-cli
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Indice RAG

Construir el indice (una sola vez, o tras cambiar los `.md` de `docs/`):

```powershell
python rag_build.py
```

## Tres interfaces disponibles

### 1. CLI mejorada (terminal)

Terminal interactiva con rich: spinner, paneles coloreados, tabla de tool calls,
comandos slash (`/help`, `/tools`, `/rag`).

```powershell
# Una sola pregunta
python cli.py "que limite de almacenamiento tiene la cuenta gratuita?"

# Modo interactivo
python cli.py
```

### 2. Web local (Streamlit)

Chat estilo ChatGPT en el navegador, con historial, expanders para ver los
tool calls y boton para reconstruir el indice RAG.

```powershell
streamlit run streamlit_app.py
```

Se abre en `http://localhost:8501`.

### 3. Plug into MCP client (VS Code / Claude Desktop)

Ya existe el archivo `.vscode/mcp.json` que registra el servidor MCP.

En **VS Code** con GitHub Copilot:
1. Abrir la carpeta del proyecto
2. Copilot Chat -> modo Agent -> activar el servidor "herramientas-locales"
3. Preguntar desde el chat de Copilot

En **Claude Desktop**, agregar al `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "herramientas-locales": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "/ruta/a/mini-cli"
    }
  }
}
```

## Herramientas MCP

- `list_files(path=".")`: lista archivos y carpetas de un directorio local.
- `fetch_url(url, max_chars=2000)`: hace GET a una URL/API y devuelve status y
  contenido truncado.

## Configuracion por variables de entorno

| Variable | Default | Descripcion |
| --- | --- | --- |
| `OLLAMA_MODEL` | `llama3.1:8b` | Modelo LLM con tool-calling |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Modelo de embeddings |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL del servidor Ollama |
| `CHROMA_DIR` | `./chroma_db` | Carpeta de la base vectorial |
| `CHROMA_COLLECTION` | `docs_rag` | Nombre de la coleccion |
| `RAG_TOP_K` | `4` | Fragmentos recuperados por consulta |
| `MAX_TOOL_ROUNDS` | `5` | Maximas rondas de herramientas por turno |

## Estructura

```
mcp_server.py       Servidor MCP (herramientas locales)
rag_build.py        Indexador RAG (LangChain + Ollama embeddings -> ChromaDB)
cli.py              CLI principal con rich (streaming + paneles + comandos)
streamlit_app.py    Web local con Streamlit (chat UI + historial)
.vscode/mcp.json    Config MCP para VS Code / Copilot
docs/               Documentos .md de prueba indexados
chroma_db/          Base vectorial local (generada por rag_build.py, gitignored)
```
