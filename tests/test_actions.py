import json

import pytest

import app.actions as actions


@pytest.fixture()
def local_action_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(actions, "PRIVATE_DATA_DIR", tmp_path)
    monkeypatch.setattr(actions, "PROPOSALS_DIR", tmp_path / "proposals")
    monkeypatch.setattr(actions, "FOLLOW_UPS_DIR", tmp_path / "follow_ups")
    monkeypatch.setattr(actions, "AUDIT_LOG", tmp_path / "audit.jsonl")


def test_action_requires_approval_before_follow_up_is_created(local_action_storage):
    _, proposal = actions.propose_action("crear_seguimiento_cliente", {
        "cliente": "Empresa Demo", "resumen": "Solicita una demostración.", "prioridad": "alta"
    })
    assert proposal and proposal["status"] == "pending"
    assert not list(actions.FOLLOW_UPS_DIR.glob("*.json"))

    follow_up = actions.approve_action(proposal["id"], "operador_demo")
    assert follow_up["cliente"] == "Empresa Demo"
    assert json.loads((actions.FOLLOW_UPS_DIR / f"{proposal['id']}.json").read_text(encoding="utf-8"))["prioridad"] == "alta"
