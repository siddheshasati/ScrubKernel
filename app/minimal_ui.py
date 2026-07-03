"""
Claude-style minimal chat UI for the agent app.
"""

import streamlit as st

from app.auth import authenticate, create_account
from app.config import get_groq_api_key
from app.mcp_servers import mcp_registry
from app.theme import inject_claude_theme, render_brand_header
from app.tools import archive_files_after_approval, execute_workspace_command
from app.audit import record_tool_event
from app.workspace import initialize_environment


SUGGESTION_PROMPTS = [
    "Create a banking application",
    "List files in the demo workspace",
    "Analyze code quality in a generated project",
]


def bootstrap_minimal_session() -> None:
    defaults = {
        "messages": [],
        "auth_user": None,
        "use_uploaded_context": True,
        "require_human_approval": True,
        "require_command_approval": True,
        "pending_archive_action": None,
        "pending_command_action": None,
        "audit_logs": [],
        "upload_results": [],
        "mcp_console": ["[MCP] Local edge node online."],
        "pending_prompt": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _render_auth_panel() -> None:
    with st.container(border=True):
        st.markdown("#### Sign in to continue")
        tab_signin, tab_create = st.tabs(["Sign In", "Create Account"])

        with tab_signin:
            with st.form("minimal_sign_in", clear_on_submit=False):
                username = st.text_input("Username", key="signin_username")
                password = st.text_input("Password", type="password", key="signin_password")
                submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")
                if submitted:
                    ok, message, user_data = authenticate(username, password)
                    if ok and user_data:
                        st.session_state.auth_user = user_data
                        st.rerun()
                    st.error(message)

        with tab_create:
            with st.form("minimal_create", clear_on_submit=False):
                display_name = st.text_input("Display name", key="create_display_name")
                username = st.text_input("Username", key="create_username_min")
                password = st.text_input("Password", type="password", key="create_password_min")
                submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")
                if submitted:
                    ok, message = create_account(username, password, display_name)
                    if ok:
                        signed_in, _, user_data = authenticate(username, password)
                        if signed_in and user_data:
                            st.session_state.auth_user = user_data
                        st.success(message)
                        st.rerun()
                    st.error(message)


def _render_sidebar() -> None:
    with st.sidebar:
        render_brand_header()
        st.divider()

        user = st.session_state.get("auth_user")
        if user:
            st.caption(f"Signed in as **{user['display_name']}**")
            if st.button("Sign out", use_container_width=True, key="sidebar_signout"):
                st.session_state.auth_user = None
                st.session_state.messages = []
                st.session_state.pending_prompt = None
                st.rerun()
        else:
            st.info("Sign in on the main screen to chat with the agent.")

        st.divider()
        st.markdown("**MCP servers**")
        for server in mcp_registry.list_servers():
            with st.expander(server["name"], expanded=False):
                for tool in server.get("tools", []):
                    st.caption(f"· {tool['name']}")

        st.divider()
        if get_groq_api_key():
            st.success("Groq API connected")
        else:
            st.error("Add GROQ_API_KEY to `.env`")

        st.session_state.use_uploaded_context = st.checkbox(
            "Use uploaded RAG context",
            value=bool(st.session_state.get("use_uploaded_context", True)),
            key="sidebar_use_rag",
        )

        if st.button("Reset demo workspace", use_container_width=True, key="reset_demo_ws"):
            initialize_environment(reset=True)
            st.session_state.pending_archive_action = None
            st.session_state.pending_command_action = None
            st.rerun()


def _render_pending_approvals() -> None:
    pending_archive = st.session_state.get("pending_archive_action")
    if pending_archive:
        st.warning("Approval needed to archive: " + ", ".join(pending_archive["filenames"]))
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Approve archive", type="primary", use_container_width=True, key="approve_archive"):
                result = archive_files_after_approval(pending_archive["filenames_string"], approved=True)
                st.session_state.messages.append({"role": "assistant", "content": result})
                st.rerun()
        with c2:
            if st.button("Deny archive", use_container_width=True, key="deny_archive"):
                st.session_state.pending_archive_action = None
                record_tool_event("safe_archive_files", "BLOCKED", "Denied by user.")
                st.rerun()

    pending_cmd = st.session_state.get("pending_command_action")
    if pending_cmd:
        st.warning(f"Approval needed to run: `{pending_cmd['command']}`")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Approve command", type="primary", use_container_width=True, key="approve_command"):
                result = execute_workspace_command(
                    pending_cmd["command"], cwd=pending_cmd["cwd"], approved=True
                )
                st.session_state.pending_command_action = None
                st.session_state.messages.append({"role": "assistant", "content": result})
                st.rerun()
        with c2:
            if st.button("Deny command", use_container_width=True, key="deny_command"):
                st.session_state.pending_command_action = None
                record_tool_event("run_workspace_command", "BLOCKED", "Denied by user.")
                st.rerun()


def _render_suggestions() -> None:
    cols = st.columns(len(SUGGESTION_PROMPTS))
    for idx, (col, prompt) in enumerate(zip(cols, SUGGESTION_PROMPTS)):
        with col:
            if st.button(prompt, use_container_width=True, key=f"suggest_{idx}"):
                st.session_state.pending_prompt = prompt
                st.rerun()


def _render_greeting() -> None:
    name = (st.session_state.get("auth_user") or {}).get("display_name", "there")
    st.markdown(
        f'<p class="claude-greeting">Hello, {name}.<br>What should we build today?</p>',
        unsafe_allow_html=True,
    )
    _render_suggestions()


def _run_agent_reply(prompt: str) -> str:
    api_key = get_groq_api_key()
    if not api_key:
        return "Add `GROQ_API_KEY` to your `.env` file, then restart the app."
    from app.agent import run_agent_stream

    return run_agent_stream(prompt, api_key)


def _handle_user_prompt(prompt: str) -> None:
    prompt = prompt.strip()
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response = _run_agent_reply(prompt)
        if response.startswith("Agent execution failed") or response.startswith("❌"):
            st.error(response)
        else:
            st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})


def render_minimal_chat() -> None:
    if not st.session_state.get("auth_user"):
        _render_auth_panel()
        return

    _render_pending_approvals()

    pending = st.session_state.pop("pending_prompt", None)
    if pending:
        _handle_user_prompt(pending)
        return

    if not st.session_state.messages:
        _render_greeting()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Message the agent…", key="main_chat_input"):
        _handle_user_prompt(prompt)


def render_minimal_main() -> None:
    inject_claude_theme()
    bootstrap_minimal_session()
    _render_sidebar()

    st.markdown("---")
    render_brand_header()
    render_minimal_chat()
