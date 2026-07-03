from datetime import datetime
from typing import Any

import streamlit as st

from app.config import PROTOCOL_NAME


def mcp_envelope(tool_name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the local JSON-RPC/MCP-style envelope for a tool call."""

    return {
        "jsonrpc": "2.0",
        "method": f"tools/{tool_name}",
        "params": payload or {},
        "protocol": PROTOCOL_NAME,
        "client_node": "hexaware-agentverse-edge-local",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


def record_tool_event(tool_name: str, status: str, detail: str = "") -> None:
    """Append a row to the sidebar enterprise audit table."""

    # Ensure audit_logs is initialized
    if "audit_logs" not in st.session_state:
        st.session_state.audit_logs = []

    st.session_state.audit_logs.append(
        {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Tool Called": tool_name,
            "Status": status,
            "Executing Protocol": PROTOCOL_NAME,
        }
    )
    st.session_state.last_tool_event = {
        "tool": tool_name,
        "status": status,
        "detail": detail,
        "envelope": mcp_envelope(tool_name, {"detail": detail}),
    }
    st.toast(f"{PROTOCOL_NAME} invoked {tool_name}: {status}")


def render_tool_event_status() -> None:
    """Show the latest Perceive -> Plan -> Execute -> Reflect event."""

    event = st.session_state.get("last_tool_event")
    if not event:
        return

    state = "complete" if event["status"] == "ALLOWED" else "error"
    with st.status(
        f"Live Agent Loop: Perceive -> Plan -> Execute -> Reflect via {event['tool']}",
        state=state,
        expanded=False,
    ):
        st.write(f"Tool: `{event['tool']}`")
        st.write(f"Decision: `{event['status']}`")
        if event.get("detail"):
            st.write(event["detail"])
        st.json(event["envelope"], expanded=False)
