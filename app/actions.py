"""Acciones empresariales locales con aprobación humana y auditoría."""

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

PRIVATE_DATA_DIR = Path(os.environ.get("PRIVATE_DATA_DIR", "./private_data")).resolve()
PROPOSALS_DIR = PRIVATE_DATA_DIR / "proposals"
FOLLOW_UPS_DIR = PRIVATE_DATA_DIR / "follow_ups"
AUDIT_LOG = PRIVATE_DATA_DIR / "audit.jsonl"
VALID_PRIORITIES = {"baja", "normal", "alta"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _prepare_storage() -> None:
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    FOLLOW_UPS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _audit(event: str, details: dict) -> None:
    _prepare_storage()
    record = {"timestamp": _now(), "event": event, **details}
    with AUDIT_LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def action_schemas() -> list[dict]:
    """Esquemas que el modelo puede solicitar; ninguna acción se ejecuta sin aprobar."""
    return [{
        "type": "function",
        "function": {
            "name": "crear_seguimiento_cliente",
            "description": "Propone un seguimiento interno para un cliente. Requiere aprobación humana antes de guardarse.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente": {"type": "string", "description": "Nombre de la empresa o contacto"},
                    "resumen": {"type": "string", "description": "Motivo concreto del seguimiento"},
                    "prioridad": {"type": "string", "enum": ["baja", "normal", "alta"]},
                },
                "required": ["cliente", "resumen"],
            },
        },
    }]


def _clean_text(value: object, field: str, max_length: int) -> str:
    text = str(value or "").strip()
    if not text or len(text) > max_length or not re.fullmatch(r"[\s\wáéíóúüñÁÉÍÓÚÜÑ.,;:()¿?¡!&@/+\-]+", text):
        raise ValueError(f"El campo '{field}' no es válido.")
    return text


def propose_action(name: str, arguments: dict) -> tuple[str, dict | None]:
    """Valida y persiste una propuesta; nunca ejecuta el efecto empresarial."""
    if name != "crear_seguimiento_cliente":
        return "Acción no permitida en este asistente privado.", None
    try:
        payload = {
            "cliente": _clean_text(arguments.get("cliente"), "cliente", 120),
            "resumen": _clean_text(arguments.get("resumen"), "resumen", 1_000),
            "prioridad": str(arguments.get("prioridad") or "normal").lower(),
        }
        if payload["prioridad"] not in VALID_PRIORITIES:
            raise ValueError("La prioridad debe ser baja, normal o alta.")
    except ValueError as exc:
        return f"No se pudo proponer la acción: {exc}", None

    _prepare_storage()
    proposal = {"id": uuid.uuid4().hex, "action": name, "status": "pending", "created_at": _now(), "arguments": payload}
    _write_json(PROPOSALS_DIR / f"{proposal['id']}.json", proposal)
    _audit("action_proposed", {"proposal_id": proposal["id"], "action": name})
    return "Seguimiento preparado y pendiente de aprobación humana.", proposal


def approve_action(proposal_id: str, approved_by: str = "operador_local") -> dict:
    """Aprueba una propuesta pendiente y crea el registro empresarial local."""
    if not re.fullmatch(r"[a-f0-9]{32}", proposal_id):
        raise ValueError("Identificador de propuesta inválido.")
    path = PROPOSALS_DIR / f"{proposal_id}.json"
    if not path.is_file():
        raise ValueError("No se encontró la propuesta.")
    proposal = json.loads(path.read_text(encoding="utf-8"))
    if proposal.get("status") != "pending":
        raise ValueError("La propuesta ya fue procesada.")

    proposal["status"] = "approved"
    proposal["approved_at"] = _now()
    proposal["approved_by"] = _clean_text(approved_by, "approved_by", 80)
    _write_json(path, proposal)
    follow_up = {"id": proposal_id, "created_at": proposal["approved_at"], **proposal["arguments"]}
    _write_json(FOLLOW_UPS_DIR / f"{proposal_id}.json", follow_up)
    _audit("action_approved", {"proposal_id": proposal_id, "action": proposal["action"], "approved_by": proposal["approved_by"]})
    return follow_up
