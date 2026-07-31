"""Servidor MCP local con herramientas de sistema.

Expone dos herramientas:
  - list_files: lista archivos de una carpeta local.
  - fetch_url: hace GET a una URL/API y devuelve el status y parte del cuerpo.
"""

import os
import time

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("herramientas-locales")


@mcp.tool()
def list_files(path: str = ".") -> str:
    """Lista los archivos y carpetas de un directorio local (nombre, tamano y fecha). El directorio actual del proyecto es '.' (por defecto); usa rutas relativas o absolutas de Windows."""
    path = os.path.abspath(path or ".")
    if not os.path.isdir(path):
        return f"Error: '{path}' no es un directorio valido."

    lines = [f"Directorio: {path}", ""]
    try:
        entries = sorted(os.scandir(path), key=lambda e: e.name.lower())
    except OSError as exc:
        return f"Error al leer el directorio: {exc}"

    for entry in entries:
        try:
            stat = entry.stat()
            if entry.is_dir():
                lines.append(f"[DIR]  {entry.name}/")
            else:
                size = stat.st_size
                kind = f"{size} bytes"
                if size >= 1024 ** 3:
                    kind = f"{size / 1024 ** 3:.2f} GB"
                elif size >= 1024 ** 2:
                    kind = f"{size / 1024 ** 2:.2f} MB"
                elif size >= 1024:
                    kind = f"{size / 1024:.1f} KB"
                modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime))
                lines.append(f"      {entry.name}  ({kind}, modificado {modified})")
        except OSError:
            lines.append(f"      {entry.name}  (no accesible)")

    return "\n".join(lines)


@mcp.tool()
def fetch_url(url: str, max_chars: int = 2000) -> str:
    """Hace una peticion GET a una URL o API publica y devuelve el codigo de estado y el contenido (truncado)."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return f"Error: URL invalida: {url}"

    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        return f"Error de conexion: {exc}"

    body = response.text or ""
    snippet = body.replace("\n", " ").replace("\r", " ")
    snippet = " ".join(snippet.split())
    if max_chars > 0:
        snippet = snippet[:max_chars]

    return (
        f"URL: {url}\n"
        f"Status: {response.status_code} {response.reason_phrase}\n"
        f"Content-Type: {response.headers.get('content-type', 'desconocido')}\n"
        f"Contenido:\n{snippet}"
    )


if __name__ == "__main__":
    mcp.run()
