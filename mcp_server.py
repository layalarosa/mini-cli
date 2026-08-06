"""Servidor MCP local con herramientas de sistema.

Expone dos herramientas:
  - list_files: lista archivos de una carpeta local.
  - fetch_url: hace GET a una URL/API y devuelve el status y parte del cuerpo.
"""

import os
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("herramientas-locales")
PROJECT_ROOT = Path(__file__).resolve().parent


def resolve_project_path(path: str) -> Path:
    """Devuelve una ruta existente solo si queda dentro del proyecto."""
    candidate = (PROJECT_ROOT / (path or ".")).resolve()
    try:
        candidate.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError("La ruta debe estar dentro del directorio del proyecto.") from exc
    return candidate


@mcp.tool()
def list_files(path: str = ".") -> str:
    """Lista archivos del proyecto (nombre, tamaño y fecha). Usa rutas relativas a su raíz."""
    try:
        directory = resolve_project_path(path)
    except ValueError as exc:
        return f"Error: {exc}"
    if not directory.is_dir():
        return f"Error: '{path}' no es un directorio válido del proyecto."

    lines = [f"Directorio: {directory.relative_to(PROJECT_ROOT) or '.'}", ""]
    try:
        entries = sorted(os.scandir(directory), key=lambda e: e.name.lower())
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
    """Inhabilitada: el asistente empresarial no realiza solicitudes externas."""
    return "Error: fetch_url está deshabilitada para proteger información empresarial privada."


if __name__ == "__main__":
    mcp.run()
