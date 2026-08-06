"""Portal local-first de atención y operaciones para AcmeCloud."""

import asyncio
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.actions import action_schemas, approve_action, propose_action
from app.chat_service import run_conversation, validate_local_ollama_url

SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "soporte@empresa.local")
CUSTOMER_SUGGESTIONS = [
    ("¿Qué incluye el plan gratuito?", "Plan gratuito"),
    ("Compara los planes Pro y Business", "Comparar planes"),
    ("¿Cómo funciona compartir un archivo?", "Compartir archivos"),
    ("¿Cuál es el límite de tamaño por archivo?", "Límites de archivos"),
]
EMPLOYEE_SUGGESTIONS = [
    ("Resume cómo funciona la autenticación de AcmeCloud", "Seguridad"),
    ("¿Cómo se sube un archivo mediante la API?", "Consultar API"),
    ("Crea un seguimiento para Cliente Ejemplo: solicita una demostración. Prioridad alta.", "Crear seguimiento"),
]

st.set_page_config(page_title="AcmeCloud | Asistente privado", page_icon="☁️", layout="centered")
st.markdown("""<style>
.block-container {max-width: 900px; padding-top: 2.3rem;}
.hero {padding: 1.1rem 0 1.5rem;} .hero h1 {margin-bottom:.3rem; font-size:2.2rem;}
.hero p {color:#57606a; font-size:1.05rem;} .stButton > button {border-radius:10px; min-height:2.7rem;}
</style>""", unsafe_allow_html=True)


def ask(question: str) -> None:
    st.session_state.pending_question = question


def get_response(question: str, employee_mode: bool) -> tuple[str, list[dict], list[dict]]:
    proposals: list[dict] = []

    async def handle_action(name: str, arguments: dict) -> str:
        message, proposal = propose_action(name, arguments)
        if proposal:
            proposals.append(proposal)
        return message

    schemas = action_schemas() if employee_mode else []
    answer, log = asyncio.run(
        run_conversation(question, schemas, handle_action, st.session_state.messages[:-1])
    )
    return answer, log, proposals


def render_proposals(proposals: list[dict]) -> None:
    for proposal in proposals:
        args = proposal["arguments"]
        with st.container(border=True):
            st.markdown("**Acción pendiente de aprobación**")
            st.caption(f"Seguimiento · {args['prioridad'].capitalize()} · {args['cliente']}")
            st.write(args["resumen"])
            if proposal["status"] == "pending":
                if st.button("Aprobar y guardar", key=f"approve_{proposal['id']}", type="primary"):
                    try:
                        follow_up = approve_action(proposal["id"])
                        st.success(f"Seguimiento guardado localmente para {follow_up['cliente']}.")
                        proposal["status"] = "approved"
                    except ValueError as exc:
                        st.error(str(exc))
            else:
                st.success("Acción aprobada y registrada localmente.")


if "messages" not in st.session_state:
    st.session_state.messages = []

try:
    validate_local_ollama_url()
    local_status = "Modelo local conectado"
except RuntimeError as exc:
    local_status = str(exc)

with st.sidebar:
    st.markdown("## ☁️ AcmeCloud")
    st.caption("Asistente empresarial privado")
    audience = st.radio("Espacio de trabajo", ["Atención a clientes", "Equipo interno"])
    employee_mode = audience == "Equipo interno"
    st.divider()
    st.markdown("**Privacidad local**")
    st.caption("Documentos, modelo, conversaciones y acciones se procesan en la infraestructura local.")
    st.caption(f"Estado: {local_status}")
    if not employee_mode:
        st.link_button("Contactar al equipo", f"mailto:{SUPPORT_EMAIL}", use_container_width=True)
    if st.session_state.messages and st.button("Nueva conversación", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

title = "¿Cómo podemos ayudarte?" if not employee_mode else "Asistente interno"
subtitle = (
    "Planes, almacenamiento, colaboración y preguntas frecuentes."
    if not employee_mode else "Consulta políticas y procesos; las acciones siempre requieren aprobación humana."
)
st.markdown(f"<div class='hero'><h1>{title}</h1><p>{subtitle}</p></div>", unsafe_allow_html=True)

if not st.session_state.messages:
    if not employee_mode:
        metrics = st.columns(3)
        metrics[0].metric("Plan gratuito", "5 GB")
        metrics[1].metric("Plan Pro", "1 TB")
        metrics[2].metric("Plan Business", "5 TB")
        st.caption("Consulta límites, precios y funciones antes de elegir un plan.")
    st.markdown("#### Preguntas sugeridas")
    suggestions = EMPLOYEE_SUGGESTIONS if employee_mode else CUSTOMER_SUGGESTIONS
    columns = st.columns(2)
    for index, (question, label) in enumerate(suggestions):
        if columns[index % 2].button(label, key=f"suggestion_{audience}_{index}", use_container_width=True):
            ask(question)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("proposals"):
            render_proposals(message["proposals"])

question = st.session_state.pop("pending_question", None)
if typed_question := st.chat_input("Escribe tu pregunta"):
    question = typed_question

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Consultando conocimiento privado..."):
                answer, _, proposals = get_response(question, employee_mode)
            st.markdown(answer)
            if proposals:
                render_proposals(proposals)
        except Exception as exc:
            answer = (
                "No pude responder en este momento. Verifica que Ollama esté activo, "
                "que el modelo local esté instalado y que el índice se haya creado.\n\n"
                f"Detalle técnico: `{exc}`"
            )
            proposals = []
            st.error(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer, "proposals": proposals})
