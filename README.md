# AcmeCloud CLI

Herramienta local de línea de comandos para consultar documentación privada con RAG, Ollama y herramientas MCP. No incluye interfaz web ni historial de chat.

## Requisitos

- Python 3.10+
- [Ollama](https://ollama.com) ejecutándose localmente con:
  - `ollama pull qwen3.5:2b`
  - `ollama pull nomic-embed-text`

## Instalación

```powershell
git clone https://github.com/layalarosa/mini-cli.git
cd mini-cli
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Usa `.env.example` como referencia para configurar Ollama y el índice local.

## Crear el índice

Ejecuta esto una vez, o después de modificar documentos en `docs/`:

```powershell
python rag_build.py
```

## Uso del CLI

```powershell
# Consultar la documentación usando Ollama y las herramientas locales
python cli.py ask "¿Qué límite de almacenamiento tiene la cuenta gratuita?"

# Ver solo los fragmentos recuperados del índice
python cli.py rag "límites de almacenamiento"

# Ver las herramientas MCP disponibles
python cli.py tools
```

Para ver todos los argumentos:

```powershell
python cli.py --help
```

## Privacidad

- `OLLAMA_BASE_URL` solo admite `localhost`, `127.0.0.1` o `::1`.
- La aplicación no realiza solicitudes web externas.
- Documentos, índice y consultas permanecen en el equipo local.

## Pruebas

```powershell
python -m pytest -q
```

## Configuración

| Variable | Predeterminado | Descripción |
| --- | --- | --- |
| `OLLAMA_MODEL` | `qwen3.5:2b` | Modelo local con soporte para herramientas |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Modelo de embeddings |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL del servidor Ollama local |
| `CHROMA_DIR` | `./chroma_db` | Carpeta de la base vectorial |
| `CHROMA_COLLECTION` | `docs_rag` | Colección del índice |
| `RAG_TOP_K` | `4` | Fragmentos recuperados por consulta |
| `MAX_TOOL_ROUNDS` | `5` | Máximo de rondas de herramientas |
