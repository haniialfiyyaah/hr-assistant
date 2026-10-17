"""Streamlit client for the HR Policy and Leave Assistant.

Talks only to the HTTP API. Identity comes from the selected demo persona token.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import httpx
import streamlit as st

from ui_contract import API_PATHS, load_personas, select_persona


API_URL = os.getenv("API_URL", "http://localhost:8000")


def request(method: str, path: str, token: str, **kwargs):
    headers = {"Authorization": f"Bearer {token}"}
    response = httpx.request(method, f"{API_URL}{path}", headers=headers, timeout=60, **kwargs)
    if response.is_error:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:  # noqa: BLE001
            detail = response.text
        st.error(f"API {response.status_code}: {detail}")
        return None
    return response.json()


st.set_page_config(
    page_title="HR Policy and Leave Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.5rem; max-width: 1100px; }
      div[data-testid="stMetricValue"] { font-size: 1.35rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("HR Policy and Leave Assistant")
st.caption(
    "Ask about HR policies with citations, check your own leave balance, "
    "and prepare a leave request. Leave is created as pending only after you confirm. "
    "Demo data and tokens are synthetic."
)

personas = load_personas(Path(__file__).with_name("demo_personas.json"))
with st.sidebar:
    st.subheader("Signed-in persona")
    persona = st.selectbox(
        "Demo identity",
        personas,
        format_func=lambda item: item["label"],
        help="Switching persona clears the previous chat and confirmation keys.",
    )
    select_persona(st.session_state, persona)
    st.write(persona["scenario"])
    st.divider()
    st.caption(f"Employee ID: `{persona['employee_id']}`")
    st.caption(f"API: `{API_URL}`")
    st.caption("Identity is enforced by the server from the bearer token.")

token = persona["demo_token"]
chat_tab, leave_tab, monitor_tab = st.tabs(["Conversation", "My leave requests", "Monitoring"])

with chat_tab:
    st.markdown("#### Ask a question or request")
    message = st.text_area(
        "Message",
        placeholder="Examples: How many annual leave days do I get? What is my leave balance?",
        label_visibility="collapsed",
        height=120,
    )
    send = st.button("Send", type="primary", disabled=not bool(message.strip()))
    if send:
        with st.spinner("Working…"):
            result = request("POST", API_PATHS["chat"], token, json={"message": message})
        if result:
            st.session_state["last_chat"] = result

    result = st.session_state.get("last_chat")
    if result:
        st.divider()
        st.markdown(result["answer"])
        meta_cols = st.columns(2)
        meta_cols[0].caption(f"Outcome: **{result['outcome']}**")
        meta_cols[1].caption(f"Trace: `{result['trace_id']}`")

        citations = result.get("citations") or []
        if citations:
            with st.expander("Policy sources", expanded=True):
                for citation in citations:
                    st.markdown(
                        f"**{citation['document_id']}** — {citation.get('section', '')}"
                    )
                    st.write(citation.get("excerpt", ""))

        tools = result.get("tool_calls") or []
        if tools:
            with st.expander("Tools used"):
                for tool in tools:
                    st.write(f"`{tool['name']}` · {tool['status']} · {tool.get('duration_ms', 0)} ms")

        proposal = result.get("action_proposal")
        if proposal:
            st.warning(
                "A leave request has **not** been created yet. Review the proposal, "
                "then confirm to open a pending manager review."
            )
            details = st.columns(3)
            details[0].markdown(f"**Type**  \n{proposal.get('leave_type')}")
            details[1].markdown(
                f"**Dates**  \n{proposal.get('start_date')} → {proposal.get('end_date')}"
            )
            details[2].markdown(f"**Business days**  \n{proposal.get('business_days')}")
            if proposal.get("reason"):
                st.caption(f"Reason: {proposal['reason']}")
            with st.expander("Full proposal payload"):
                st.json(proposal)

            key_name = f"idem_{proposal['proposal_id']}"
            st.session_state.setdefault(key_name, str(uuid.uuid4()))
            if st.button(
                "Confirm pending leave request",
                type="primary",
                key=proposal["proposal_id"],
            ):
                confirmed = request(
                    "POST",
                    API_PATHS["confirm"].format(proposal_id=proposal["proposal_id"]),
                    token,
                    json={"idempotency_key": st.session_state[key_name]},
                )
                if confirmed:
                    st.success(
                        f"Created `{confirmed['request_id']}` with status "
                        f"**{confirmed['status']}**"
                        + (" (idempotent replay)" if confirmed.get("idempotent_replay") else "")
                    )

with leave_tab:
    st.markdown("#### Requests for the signed-in employee only")
    st.caption("The API never returns another person’s leave rows.")
    if st.button("Load my leave requests", type="primary"):
        data = request("GET", API_PATHS["my_requests"], token)
        if data is not None:
            if data:
                st.dataframe(data, use_container_width=True)
            else:
                st.info("No leave requests yet for this persona.")

with monitor_tab:
    st.markdown("#### Operational summary")
    st.info("Use the monitoring admin persona to load aggregate metrics and alerts.")
    if st.button("Load monitoring", type="primary"):
        summary = request("GET", API_PATHS["monitoring_summary"], token)
        alerts = request("GET", API_PATHS["monitoring_alerts"], token)
        if summary:
            columns = st.columns(4)
            columns[0].metric("Runs", summary["run_count"])
            columns[1].metric("Error rate", f"{float(summary['error_rate']):.1%}")
            columns[2].metric("p95 latency", f"{int(summary['p95_latency_ms'])} ms")
            columns[3].metric("Tool calls", summary["tool_calls"])
        if alerts is not None:
            st.subheader("Active alerts")
            if alerts:
                st.json(alerts)
            else:
                st.caption("No alerts are currently triggered.")
