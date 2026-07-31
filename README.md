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
pip install -r requirements.txt
```

## Uso

Construir el indice RAG (una sola vez, o tras cambiar los `.md`):

```powershell
python rag_build.py
```

Hacer una pregunta puntual:

```powershell
python cli.py "que limite de almacenamiento tiene la cuenta gratuita?"
```

Modo interactivo:

```powershell
python cli.py
```

## Ejemplos verificados

```
> que limite de almacenamiento tiene la cuenta gratuita de AcmeCloud?
  [MCP] list_files({"path": "/docs/intro.md"})
... la cuenta gratuita incluye 5 GB de almacenamiento. (Fuente: docs\intro.md)

> usa la herramienta list_files para mostrar los archivos del directorio actual
  [MCP] list_files({"path": "."})
  -> lista real de archivos del proyecto

> usa fetch_url para consultar la API https://httpbin.org/json
  [MCP] fetch_url({"url": "https://httpbin.org/json", ...})
  -> resumen de la respuesta JSON de la API
```

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

## Herramientas MCP

- `list_files(path=".")`: lista archivos y carpetas de un directorio local.
- `fetch_url(url, max_chars=2000)`: hace GET a una URL/API y devuelve status y
  contenido truncado.

## Estructura

```
mcp_server.py   Servidor MCP (herramientas locales)
rag_build.py    Indexador RAG (LangChain + Ollama embeddings -> ChromaDB)
cli.py          CLI principal (RAG + MCP tools + Ollama tool-calling)
docs/           Documentos .md de prueba indexados
chroma_db/      Base vectorial local (generada por rag_build.py)
```
