import pandas as pd
import streamlit as st
import ast
import re
import time
from pathlib import Path

from app.agent import run_agent_stream
from app.audit import record_tool_event, render_tool_event_status, mcp_envelope
from app.auth import authenticate, create_account
from app.config import APP_TITLE, EVENT_NAME, PROJECTS_DIR, PROTOCOL_NAME, WORKSPACE_ROOT, get_groq_api_key
from app.rag import save_and_index_upload
from app.sample_data import PROJECT_STRUCTURE_GUIDE
from app.tools import archive_files_after_approval, execute_workspace_command
from app.workspace import initialize_environment
from app.mcp_servers import mcp_registry


def inject_css() -> None:
    # Use the theme's CSS injector
    from app.theme import inject_claude_theme
    inject_claude_theme()


def bootstrap_session_state() -> None:
    st.session_state.setdefault(
        "messages",
        [
            {
                "role": "assistant",
                "content": "Hello! I am your Advanced OS Automation Agent. I can generate projects, inspect files, check logs, and run safe commands. Ask me anything to get started!",
            }
        ],
    )
    st.session_state.setdefault("audit_logs", [])
    st.session_state.setdefault("pending_archive_action", None)
    st.session_state.setdefault("last_tool_event", None)
    st.session_state.setdefault("require_human_approval", True)
    st.session_state.setdefault("require_command_approval", True)
    st.session_state.setdefault("pending_command_action", None)
    st.session_state.setdefault("auth_user", None)
    st.session_state.setdefault("upload_results", [])
    st.session_state.setdefault("use_uploaded_context", True)
    st.session_state.setdefault("running_processes", [])
    st.session_state.setdefault(
        "mcp_console",
        [
            "[MCP Server] Local protocol wrapper online at mcp://localhost/hexaware-agentverse-edge."
        ],
    )


# ============================================================================
# HELPER ACTIONS (Direct access to files outside Agent sandbox constraints)
# ============================================================================

def get_workspace_files():
    initialize_environment(reset=False)
    demo_files = sorted(
        str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
        for path in WORKSPACE_ROOT.rglob("*")
        if path.is_file()
    )
    project_files = sorted(
        str(path.relative_to(PROJECTS_DIR)).replace("\\", "/")
        for path in PROJECTS_DIR.rglob("*")
        if path.is_file()
    )
    return demo_files, project_files


def read_file_content(area: str, rel_path: str) -> tuple[str, int]:
    base_dir = WORKSPACE_ROOT if area == "demo_workspace" else PROJECTS_DIR
    target_path = (base_dir / rel_path).resolve()
    try:
        content = target_path.read_text(encoding="utf-8", errors="replace")
        return content, len(content)
    except Exception as e:
        return f"Error reading file: {str(e)}", 0


def analyze_quality_local(content: str, filename: str) -> str:
    lines = content.split('\n')
    metrics = {
        "total_lines": len(lines),
        "code_lines": len([l for l in lines if l.strip() and not l.strip().startswith('#')]),
        "comment_lines": len([l for l in lines if l.strip().startswith('#')]),
        "blank_lines": len([l for l in lines if not l.strip()]),
    }
    
    try:
        tree = ast.parse(content)
        functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        metrics["functions"] = len(functions)
        metrics["classes"] = len(classes)
        metrics["avg_function_length"] = int(sum(len(f.body) for f in functions) / len(functions)) if functions else 0
        
        complexity_scores = []
        for func in functions:
            branches = sum(1 for node in ast.walk(func) if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler)))
            complexity_scores.append(branches)
        metrics["avg_cyclomatic_complexity"] = sum(complexity_scores) / len(complexity_scores) if complexity_scores else 0
        metrics["max_function_complexity"] = max(complexity_scores) if complexity_scores else 0
    except SyntaxError as e:
        return f"Syntax error in file: {e}"

    comment_ratio = (metrics['comment_lines'] / max(metrics['code_lines'], 1)) * 100
    
    recs = []
    if comment_ratio < 10:
        recs.append("  - Add more code comments (currently <10% comment ratio)")
    if metrics.get('avg_cyclomatic_complexity', 0) > 5:
        recs.append("  - Reduce function complexity (avg >5 branches, consider refactoring)")
    if metrics.get('functions', 0) > 20:
        recs.append("  - Large file detected. Consider organizing into multiple modules")
    if not recs:
        recs.append("  - Code quality is clean. Maintain current standards!")

    return f"""CODE QUALITY AUDIT: {filename}
==================================================
Lines of Code:
- Total: {metrics['total_lines']}
- Code Lines: {metrics['code_lines']}
- Comments: {metrics['comment_lines']} ({comment_ratio:.1f}% ratio)
- Blank: {metrics['blank_lines']}

Structure:
- Functions: {metrics['functions']}
- Classes: {metrics['classes']}
- Avg Function Size: {metrics['avg_function_length']} statements
- Avg Cyclomatic Complexity: {metrics['avg_cyclomatic_complexity']:.2f}
- Max Function Complexity: {metrics['max_function_complexity']}

Recommendations:
{"\n".join(recs)}"""


def detect_security_local(content: str, filename: str) -> str:
    issues = []
    security_patterns = {
        "exec(": "🔴 CRITICAL: Use of eval/exec allows arbitrary code execution",
        "pickle.loads": "🟠 CRITICAL: Pickle deserialization can execute code",
        "eval(": "🔴 CRITICAL: eval() is dangerous, use ast.literal_eval()",
        "os.system": "🟡 MEDIUM: Use subprocess.run() instead of os.system",
        "request.form": "🟡 MEDIUM: Always validate/sanitize form input",
        "password in ": "🔴 CRITICAL: Hardcoded password detected",
        "api_key =": "🔴 CRITICAL: API key may be hardcoded",
        "secret =": "🔴 CRITICAL: Secret key may be hardcoded",
        "sql_query = f\"": "🟠 HIGH: SQL injection risk - use parameterized queries",
    }
    
    for pattern, issue in security_patterns.items():
        if pattern in content:
            issues.append(issue)
            
    if not issues:
        return f"✅ No major security issues detected in {filename}."
        
    return f"🛡️ SECURITY SCAN: {filename}\n==================================================\n" + "\n".join(f"- {issue}" for issue in issues)


def generate_docs_local(content: str, filename: str) -> str:
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return f"Syntax error: {e}"
        
    docs = f"# API Documentation: {filename}\n\n"
    found = False
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            found = True
            sig = f"{node.name}("
            if node.args.args:
                args = [arg.arg for arg in node.args.args]
                sig += ", ".join(args)
            sig += ")"
            
            docstring = ast.get_docstring(node) or "*No documentation provided.*"
            docs += f"### `function` {sig}\n{docstring}\n\n"
            
        elif isinstance(node, ast.ClassDef):
            found = True
            docs += f"## `class` {node.name}\n"
            docstring = ast.get_docstring(node) or "*No documentation provided.*"
            docs += f"{docstring}\n\n"
            
    if not found:
        docs += "*No class or function declarations found to document.*"
    return docs


def suggest_improvements_local(content: str, filename: str) -> str:
    suggestions = []
    if 'import *' in content:
        suggestions.append("❌ Avoid 'from X import *', specify what you need to prevent namespace pollution.")
    if '# TODO' in content or '# FIXME' in content:
        suggestions.append("⚠️ Contains TODO/FIXME comments - track in issues or address them.")
    if content.count('\n\n\n') > 0:
        suggestions.append("🔄 Multiple blank lines found - consolidate spacing for cleaner reading.")
    if 'try:' in content and content.count('except:') > content.count('except Exception'):
        suggestions.append("🛡️ Use specific exception types instead of bare except clause.")
    if len(content) > 40000:
        suggestions.append("📦 File is large (>40KB) - consider breaking into smaller modules.")
    if content.count('def ') > 25:
        suggestions.append("📂 Many functions in one file - consider organizing into classes.")
        
    if not suggestions:
        suggestions.append("✅ Code structure looks outstanding! No immediate improvements needed.")
        
    return f"💡 IMPROVEMENT SUGGESTIONS: {filename}\n==================================================\n" + "\n".join(f"- {s}" for s in suggestions)


# ============================================================================
# UI RENDERERS
# ============================================================================

def render_account_panel() -> None:
    with st.container(border=True):
        st.subheader("Account Hub")
        user = st.session_state.get("auth_user")
        if user:
            st.markdown(
                f'<div style="display: flex; align-items: center; margin-bottom: 12px;">'
                f'<span class="led-indicator"></span>'
                f'<span>Active Session: <strong>{user["display_name"]}</strong></span>'
                f'</div>',
                unsafe_allow_html=True
            )
            if st.button("Sign Out", use_container_width=True, key="main_signout"):
                st.session_state.auth_user = None
                st.rerun()
        else:
            sign_in, create = st.tabs(["Sign In", "Register"])
            with sign_in:
                with st.form("sign_in_form", clear_on_submit=False):
                    username = st.text_input("Username", key="signin_username_val")
                    password = st.text_input("Password", type="password", key="signin_password_val")
                    submitted = st.form_submit_button("Sign In", use_container_width=True)
                if submitted:
                    ok, message, user_data = authenticate(username, password)
                    if ok and user_data:
                        st.session_state.auth_user = user_data
                        st.success(message)
                        st.rerun()
                    st.error(message)

            with create:
                with st.form("create_account_form", clear_on_submit=False):
                    display_name = st.text_input("Display name")
                    username = st.text_input("Username", key="create_username_val")
                    password = st.text_input("Password", type="password", key="create_password_val")
                    submitted = st.form_submit_button("Create Account", use_container_width=True)
                if submitted:
                    ok, message = create_account(username, password, display_name)
                    if ok:
                        signed_in, _, user_data = authenticate(username, password)
                        if signed_in and user_data:
                            st.session_state.auth_user = user_data
                        st.success(message)
                        st.rerun()
                    st.error(message)


def render_sidebar() -> None:
    with st.sidebar:
        # Account Hub
        render_account_panel()
        
        st.divider()

        # Workspace Control Plane
        with st.container(border=True):
            st.subheader("OS Control Plane")
            
            # API Connection indicators
            api_key = get_groq_api_key()
            if api_key:
                st.markdown('<p style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary);"><span style="color: #10b981;">●</span> Groq Model Server Connected</p>', unsafe_allow_html=True)
            else:
                st.markdown('<p style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary);"><span style="color: #ef4444;">▲</span> Groq Server Disconnected</p>', unsafe_allow_html=True)
                st.caption("Please check GROQ_API_KEY in .env")

            st.session_state.require_human_approval = st.checkbox(
                "Require Human Approval for Destructive Tasks",
                value=st.session_state.require_human_approval,
                key="cb_require_human"
            )
            st.session_state.require_command_approval = st.checkbox(
                "Require Command Approval (CLI Setup/Run)",
                value=st.session_state.require_command_approval,
                key="cb_require_cmd"
            )

            if st.button("Reset Sandbox Environment", use_container_width=True, key="btn_reset_env"):
                initialize_environment(reset=True)
                st.session_state.pending_archive_action = None
                st.session_state.pending_command_action = None
                record_tool_event("reset_demo_workspace", "ALLOWED", "Demo workspace reinitialized.")
                st.success("Workspace reset completed successfully.")
                st.rerun()

        # Active Sub-processes
        if st.session_state.running_processes:
            st.divider()
            with st.container(border=True):
                st.subheader("Active Tasks / Servers")
                for process in st.session_state.running_processes[-3:]:
                    st.markdown(
                        f'<div style="font-size: 0.8rem; margin-bottom: 8px; border-left: 2px solid var(--accent-color); padding-left: 8px;">'
                        f'<strong>PID {process["pid"]}</strong>: <code>{process["command"]}</code><br>'
                        f'<span style="color: var(--text-muted)">Log: {Path(process["log"]).name}</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )


def render_pending_approvals_panel() -> None:
    pending_archive = st.session_state.get("pending_archive_action")
    pending_cmd = st.session_state.get("pending_command_action")
    
    if pending_archive:
        st.markdown(
            f'<div class="badge badge-pending" style="margin-bottom: 8px;">Human Review Required</div>',
            unsafe_allow_html=True
        )
        st.warning("Approval needed to archive: " + ", ".join(pending_archive["filenames"]))
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Approve archive", type="primary", use_container_width=True, key="approve_archive_btn"):
                result = archive_files_after_approval(pending_archive["filenames_string"], approved=True)
                st.session_state.messages.append({"role": "assistant", "content": result})
                st.rerun()
        with c2:
            if st.button("Deny archive", use_container_width=True, key="deny_archive_btn"):
                st.session_state.pending_archive_action = None
                record_tool_event("safe_archive_files", "BLOCKED", "Denied by user.")
                st.rerun()

    if pending_cmd:
        st.markdown(
            f'<div class="badge badge-pending" style="margin-bottom: 8px;">Human Review Required</div>',
            unsafe_allow_html=True
        )
        st.warning(f"Approval needed to run command: `{pending_cmd['command']}` in `{pending_cmd['cwd']}`")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Approve command", type="primary", use_container_width=True, key="approve_command_btn"):
                result = execute_workspace_command(
                    pending_cmd["command"], cwd=pending_cmd["cwd"], approved=True
                )
                st.session_state.pending_command_action = None
                st.session_state.messages.append({"role": "assistant", "content": result})
                st.rerun()
        with c2:
            if st.button("Deny command", use_container_width=True, key="deny_command_btn"):
                st.session_state.pending_command_action = None
                record_tool_event("run_workspace_command", "BLOCKED", "Denied by user.")
                st.rerun()


def render_chat_tab() -> None:
    with st.container(border=True):
        st.subheader("✦ Hexaware OS AI Agent")
        st.markdown('<p style="color: var(--text-muted); font-size: 0.85rem;">Ask the agent to create files, generate Streamlit projects, check logs, or run python scripts.</p>', unsafe_allow_html=True)
        
        # Suggestion Chips
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Create a banking application", use_container_width=True, key="sug_bank"):
                st.session_state.messages.append({"role": "user", "content": "Create a banking application"})
                with st.spinner("Agent running workflow..."):
                    response = run_agent_stream("Create a banking application", get_groq_api_key())
                    st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()
        with c2:
            if st.button("Inspect server.log & find error", use_container_width=True, key="sug_log"):
                st.session_state.messages.append({"role": "user", "content": "Read and inspect server.log and tell me the error trace details."})
                with st.spinner("Agent checking logs..."):
                    response = run_agent_stream("Read and inspect server.log and tell me the error trace details.", get_groq_api_key())
                    st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()
        with c3:
            if st.button("List all project files", use_container_width=True, key="sug_list"):
                st.session_state.messages.append({"role": "user", "content": "List files in the workspace"})
                with st.spinner("Agent fetching structure..."):
                    response = run_agent_stream("List files in the workspace", get_groq_api_key())
                    st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()

    # Chat Messages Feed
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    prompt = st.chat_input("Message the agent...", key="main_chat_input_field")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            api_key = get_groq_api_key()
            if not api_key:
                response = "Missing GROQ_API_KEY. Add it to `.env`, then restart Streamlit."
                st.error(response)
            else:
                with st.spinner("Agent is reasoning..."):
                    response = run_agent_stream(prompt, api_key)
                st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()


def render_explorer_tab() -> None:
    with st.container(border=True):
        st.subheader("📂 Sandbox Workspace Explorer")
        st.caption("View and perform direct actions on workspace and project files.")
        
        demo_files, project_files = get_workspace_files()
        
        col_sel, col_act = st.columns([1, 1])
        
        selected_file = None
        selected_area = None
        
        with col_sel:
            st.markdown("**1. Select File to Inspect**")
            area = st.radio("Choose Sandbox Area", ["Demo Workspace", "Generated Projects"], horizontal=True)
            
            if area == "Demo Workspace":
                if demo_files:
                    selected_file = st.selectbox("Select File", demo_files, key="select_demo_file")
                    selected_area = "demo_workspace"
                else:
                    st.info("No files in demo workspace.")
            else:
                if project_files:
                    selected_file = st.selectbox("Select File", project_files, key="select_proj_file")
                    selected_area = "generated_projects"
                else:
                    st.info("No generated projects yet. Ask the agent to build one!")
                    
        with col_act:
            if selected_file:
                content, size = read_file_content(selected_area, selected_file)
                st.markdown("**2. File Metadata**")
                st.markdown(
                    f"- **Filename**: `{Path(selected_file).name}`\n"
                    f"- **Path**: `{selected_area}/{selected_file}`\n"
                    f"- **Size**: `{size} characters`"
                )
                
                st.markdown("**3. Immediate Actions**")
                ac1, ac2 = st.columns(2)
                
                run_audit = False
                audit_type = None
                
                with ac1:
                    if st.button("Run Quality Audit", use_container_width=True, key="act_quality"):
                        run_audit = True
                        audit_type = "quality"
                    if st.button("Scan Security Issues", use_container_width=True, key="act_security"):
                        run_audit = True
                        audit_type = "security"
                with ac2:
                    if st.button("Generate API Docs", use_container_width=True, key="act_docs"):
                        run_audit = True
                        audit_type = "docs"
                    if st.button("Suggest Improvements", use_container_width=True, key="act_improve"):
                        run_audit = True
                        audit_type = "improve"
                        
        st.divider()
        
        if selected_file:
            if run_audit:
                st.markdown(f"### 📊 Analysis Output: `{Path(selected_file).name}`")
                with st.container(border=True):
                    if audit_type == "quality":
                        st.code(analyze_quality_local(content, selected_file), language="markdown")
                    elif audit_type == "security":
                        st.code(detect_security_local(content, selected_file), language="markdown")
                    elif audit_type == "docs":
                        st.code(generate_docs_local(content, selected_file), language="markdown")
                    elif audit_type == "improve":
                        st.code(suggest_improvements_local(content, selected_file), language="markdown")
            else:
                st.markdown(f"### 📄 Code Preview: `{Path(selected_file).name}`")
                # Determine language syntax
                suffix = Path(selected_file).suffix
                lang = "python" if suffix == ".py" else ("json" if suffix == ".json" else ("ini" if suffix == ".config" else "markdown"))
                st.code(content, language=lang)


def render_code_intel_tab() -> None:
    with st.container(border=True):
        st.subheader("🛡️ Code Intelligence & Comparative Audit")
        st.caption("Deep design pattern comparison, architectural checks, and validation.")
        
        demo_files, project_files = get_workspace_files()
        all_files = [("demo_workspace", f) for f in demo_files] + [("generated_projects", f) for f in project_files]
        
        if not all_files:
            st.info("No files available in the workspace to audit.")
            return
            
        tab_single, tab_compare = st.tabs(["Analyze File/Folder", "Compare Implementations"])
        
        with tab_single:
            st.markdown("#### Run Static Analysis tools")
            file_options = [f"{area}/{path}" for area, path in all_files]
            chosen = st.selectbox("Select Target File/Folder", file_options, key="intel_single_select")
            
            c1, c2, c3 = st.columns(3)
            action = None
            
            with c1:
                if st.button("Analyze Folder Architecture", use_container_width=True, key="intel_folder_arch"):
                    action = "folder_arch"
            with c2:
                if st.button("Validate Project Structure", use_container_width=True, key="intel_validate"):
                    action = "validate_struct"
            with c3:
                if st.button("Extract Dependency Graph", use_container_width=True, key="intel_deps"):
                    action = "extract_deps"
                    
            if action:
                area, rel_path = chosen.split('/', 1)
                # Find directory context if it is a file
                folder = str(Path(rel_path).parent).replace("\\", "/")
                if folder == "." or not folder:
                    folder = rel_path
                    
                st.markdown("##### Analysis Output")
                with st.container(border=True):
                    with st.spinner("Analyzing project layout..."):
                        if action == "folder_arch":
                            result = mcp_registry.call_tool("code_analysis", "analyze_architecture", project_path=folder)
                            st.code(result, language="json")
                        elif action == "validate_struct":
                            result = mcp_registry.call_tool("project_generation", "validate_structure", project_path=folder)
                            st.code(result, language="json")
                        elif action == "extract_deps":
                            # We can execute our local dependency extraction or tool call
                            from app.tools import extract_dependencies
                            result = extract_dependencies.func(project_folder=folder)
                            st.code(result, language="markdown")
                
        with tab_compare:
            st.markdown("#### Compare Two Implementations")
            file_options = [f"{area}/{path}" for area, path in all_files if path.endswith('.py')]
            
            if len(file_options) < 2:
                st.info("You need at least 2 Python files in the workspace to perform a comparative audit.")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    file1 = st.selectbox("File 1 (Base)", file_options, index=0, key="compare_f1")
                with col2:
                    file2 = st.selectbox("File 2 (Comparison)", file_options, index=1, key="compare_f2")
                    
                if st.button("Run Comparative Diff Analysis", type="primary", use_container_width=True, key="compare_btn"):
                    st.markdown("##### Comparison Report")
                    with st.container(border=True):
                        with st.spinner("Comparing files..."):
                            area1, p1 = file1.split('/', 1)
                            area2, p2 = file2.split('/', 1)
                            
                            content1, _ = read_file_content(area1, p1)
                            content2, _ = read_file_content(area2, p2)
                            
                            # Call tool logic
                            from app.tools import compare_implementations
                            # To remain fully safe, we pass relative paths inside workspace if they are demo_files, 
                            # otherwise we run diff directly.
                            import difflib
                            diff = difflib.unified_diff(content1.splitlines(), content2.splitlines(), lineterm='', n=1)
                            diff_lines = list(diff)
                            
                            result = f"""IMPLEMENTATION COMPARISON
==================================================
File 1: {file1} ({len(content1.splitlines())} lines)
File 2: {file2} ({len(content2.splitlines())} lines)
 
Difference Summary:
- Changed lines: {len(diff_lines)}
- Line growth: {len(content2.splitlines()) - len(content1.splitlines()):+d}
 
Key Differences (first 50 diff lines):
--------------------------------------------------
{chr(10).join(diff_lines[:50])}"""
                            st.code(result, language="markdown")

def render_logs_tab() -> None:
    with st.container(border=True):
        st.subheader("📜 Enterprise Governance Audit Logs")
        st.caption("Standardized JSON-RPC/MCP transaction envelopes and action logging.")
        
        if st.session_state.audit_logs:
            df = pd.DataFrame(st.session_state.audit_logs)
            st.dataframe(df.tail(25), hide_index=True, use_container_width=True)
        else:
            st.info("No tool calls recorded in this session yet.")
            
        st.markdown("---")
        st.subheader("Latest MCP Envelope")
        event = st.session_state.get("last_tool_event")
        if event:
            st.markdown(
                f'- **Latest Tool**: `{event["tool"]}`\n'
                f'- **Execution Status**: `{event["status"]}`\n'
                f'- **Details**: `{event["detail"]}`'
            )
            st.json(event["envelope"])
        else:
            st.caption("No envelopes captured yet.")


def render_rag_tab() -> None:
    with st.container(border=True):
        st.subheader("⚙️ Prompt Files & RAG Ingestion")
        st.caption("Upload documents to inject them into the agent's semantic memory.")
        
        user = st.session_state.get("auth_user")
        if not user:
            st.warning("Please sign in or create an account from the sidebar to access document ingestion.")
            return
            
        st.session_state.use_uploaded_context = st.checkbox(
            "Auto-inject matching document snippets into prompt context",
            value=st.session_state.use_uploaded_context,
            key="rag_auto_inject"
        )
        
        uploads = st.file_uploader(
            "Select documents or code references",
            type=["txt", "md", "csv", "json", "py", "pdf", "docx", "png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="rag_file_uploader"
        )
        
        if uploads and st.button("Index Documents", type="primary", use_container_width=True, key="rag_index_btn"):
            with st.spinner("Processing text extraction and ChromaDB embedding..."):
                results = [save_and_index_upload(user["username"], f) for f in uploads]
                st.session_state.upload_results = results
                record_tool_event("index_uploaded_context", "ALLOWED", f"Indexed {len(results)} document(s).")
                st.success(f"Successfully processed and indexed {len(results)} files!")
                st.rerun()
                
        if st.session_state.upload_results:
            st.markdown("#### Recently Indexed Files")
            for res in st.session_state.upload_results[-5:]:
                st.markdown(
                    f'<div style="font-size: 0.85rem; padding: 8px; border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 6px;">'
                    f'📄 <strong>{res["filename"]}</strong> — {res["chunks"]} chunk(s) indexed via <em>{res["indexed_with"]}</em>'
                    f'</div>',
                    unsafe_allow_html=True
                )


def render_main() -> None:
    inject_css()
    bootstrap_session_state()
    
    # Sidebar rendering
    render_sidebar()
    
    # Main dashboard header
    from app.theme import render_brand_header
    render_brand_header()
    
    # Live loop status and approvals
    render_tool_event_status()
    render_pending_approvals_panel()
    
    # Create the primary tab container
    tab_chat, tab_explorer, tab_intel, tab_logs, tab_rag = st.tabs([
        "✦ Agent Chat",
        "📂 Workspace Explorer",
        "🛡️ Code Intelligence",
        "📜 Governance Logs",
        "⚙️ RAG Settings"
    ])
    
    with tab_chat:
        render_chat_tab()
        
    with tab_explorer:
        render_explorer_tab()
        
    with tab_intel:
        render_code_intel_tab()
        
    with tab_logs:
        render_logs_tab()
        
    with tab_rag:
        render_rag_tab()
