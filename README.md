# AcmeCloud Private Assistant

Asistente de IA **local-first** para empresas. Aprende de documentación privada,
responde preguntas de clientes y empleados, y propone acciones internas con
aprobación humana y auditoría local.

No se envían documentos ni conversaciones a servicios externos: el modelo
Ollama, ChromaDB y los registros de acciones se ejecutan localmente.

El sistema une estas piezas:

1. **Servidor MCP** (`mcp_server.py`): expone herramientas locales mediante el
   protocolo MCP (stdlib).
2. **Base RAG** (`rag_build.py`): indexa los `.md` de `docs/` en ChromaDB
   usando LangChain para la carga y division de documentos y embeddings
   generados con Ollama (`nomic-embed-text`).
3. **Interfaces** (`cli.py`, `streamlit_app.py`): recuperan contexto del RAG,
   le entrega al LLM las herramientas MCP (tool-calling) y muestra la respuesta
   en pantalla.

## Requisitos

- Python 3.10+
- [Ollama](https://ollama.com) en ejecucion con los modelos:
  - `ollama pull qwen3.5:2b` (LLM local rápido con soporte de tools)
  - `ollama pull nomic-embed-text` (embeddings para el RAG)

## Instalacion

```powershell
git clone https://github.com/layalarosa/mini-cli.git
cd mini-cli
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Usa `.env.example` como referencia para definir las variables de entorno de tu
servidor local.

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

### 2. Portal empresarial privado (Streamlit)

Incluye dos espacios: atención a clientes e interfaz de equipo interno. El
equipo puede pedir acciones como crear seguimientos, pero cada acción queda
pendiente hasta que un operador la apruebe. Los registros y la auditoría quedan
en `private_data/`, carpeta excluida de Git.

```powershell
streamlit run streamlit_app.py
```

Se abre en `http://localhost:8501`.

Define `SUPPORT_EMAIL` para personalizar el botón de contacto.

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

## Privacidad y acciones

- `OLLAMA_BASE_URL` solo acepta `localhost`, `127.0.0.1` o `::1`.
- La aplicación no realiza peticiones web externas; `fetch_url` está deshabilitada.
- La única acción inicial es `crear_seguimiento_cliente`, validada, aprobada
  manualmente y auditada en un archivo local JSONL.

## Herramientas MCP

- `list_files(path=".")`: lista archivos y carpetas **dentro del proyecto**.
- `fetch_url(...)`: deshabilitada en el modo empresarial privado.

## Pruebas

```powershell
python -m pytest -q
```

## Configuracion por variables de entorno

| Variable | Default | Descripcion |
| --- | --- | --- |
| `OLLAMA_MODEL` | `qwen3.5:2b` | Modelo LLM local con tool-calling |
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
