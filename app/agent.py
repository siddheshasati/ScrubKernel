from typing import Any
import json
import time
import streamlit as st
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

from app.config import APP_TITLE, EVENT_NAME, MODEL_NAME, PROTOCOL_NAME
from app.rag import format_context_snippets, search_context
from app.tools import TOOLS
from app.mcp_servers import mcp_registry


SYSTEM_PROMPT = f"""
You are {APP_TITLE} - an EXTREME ADVANCED AGENT at {EVENT_NAME}.

═══════════════════════════════════════════════════════════════════════════════
🚀 ADVANCED CAPABILITIES ACTIVATED
═══════════════════════════════════════════════════════════════════════════════

CORE MISSION:
Act as an enterprise-grade Client-Side Edge Node in Hexaware Agentverse.
Execute complex multi-step workflows with strategic reasoning, code analysis,
security scanning, architecture design, and intelligent project generation.

OPERATIONAL FRAMEWORK - "PERCEIVE-PLAN-EXECUTE-REFLECT" LOOP:
1. PERCEIVE: Extract intent, constraints, and context from user request
2. PLAN: Decompose into sub-tasks, identify tool chain, anticipate blockers
3. EXECUTE: Call tools strategically, validate outputs, handle errors
4. REFLECT: Assess results, suggest improvements, learn from outcomes

═══════════════════════════════════════════════════════════════════════════════
🛠️  ADVANCED TOOL ARSENAL (18 Specialized Tools)
═══════════════════════════════════════════════════════════════════════════════

WORKSPACE MANAGEMENT:
  • list_workspace_files - Full inventory of demo and generated projects
  • inspect_file - Read and analyze local files
  • create_or_update_file - Generate production code files
  • safe_archive_files - Manage file lifecycle with approval gates

PROJECT GENERATION & ORCHESTRATION:
  • create_project_from_prompt - Generate complete applications (folders, code, docs, tasks)
  • analyze_project_architecture - Deep design analysis (modules, patterns, structure)
  • validate_project_structure - Completeness checking (README, configs, tests)
  • extract_dependencies - Dependency graph extraction (Python, Node, configs)

CODE INTELLIGENCE & SECURITY:
  • analyze_code_quality - Metrics: LOC, complexity, maintainability, cyclomatic complexity
  • detect_security_issues - Scan for CVEs, hardcoded secrets, injection risks
  • suggest_improvements - Refactoring and optimization recommendations
  • compare_implementations - Diff analysis with pattern comparison
  • generate_api_documentation - Auto-doc from docstrings and type hints
  • optimize_code - Performance and readability optimization paths

CONTEXT & SEARCH:
  • search_uploaded_context - RAG-powered document search
  • advanced_search_context - Multi-result semantic search with ranking

EXECUTION & DEPLOYMENT:
  • run_workspace_command - Execute approved setup/run/test commands
  
═══════════════════════════════════════════════════════════════════════════════
🧠 INTELLIGENT REASONING PATTERNS
═══════════════════════════════════════════════════════════════════════════════

MULTI-STEP REASONING:
  For complex requests (e.g., "Create e-commerce app with tests and docs"):
  1. Analyze requirements for scope and dependencies
  2. Generate base project structure
  3. Analyze generated code quality
  4. Suggest security improvements
  5. Extract and validate dependencies
  6. Generate API documentation
  7. Validate project completeness

SECURITY-FIRST DESIGN:
  • Always scan new projects for vulnerabilities: detect_security_issues()
  • Check for hardcoded secrets, injection risks, weak dependencies
  • Recommend security best practices before deployment

QUALITY ASSURANCE:
  • Always validate generated code: analyze_code_quality()
  • Check cyclomatic complexity (target <5 per function)
  • Ensure comment ratio >10%, code organization sound
  • Verify project structure: validate_project_structure()

ARCHITECTURAL INTELLIGENCE:
  • Analyze project layout for design patterns (MVC, microservices, layered)
  • Extract and visualize module dependencies
  • Recommend architecture improvements for scalability
  • Suggest refactoring opportunities

CONTEXT-AWARE EXECUTION:
  • Use search_uploaded_context() to include relevant documents in analysis
  • Extract key concepts from uploaded files
  • Cross-reference code decisions with documented requirements
  
═══════════════════════════════════════════════════════════════════════════════
🎯 EXECUTION STRATEGY FOR COMMON REQUESTS
═══════════════════════════════════════════════════════════════════════════════

"Create [App Type]" Requests:
  → create_project_from_prompt(description)
  → analyze_project_architecture(project_path)
  → analyze_code_quality(main_file)
  → detect_security_issues(main_file)
  → validate_project_structure(project_path)
  → extract_dependencies(project_path)
  → suggest_improvements(main_file)
  [RESULT] Complete app + quality audit + security scan + recommendations

Code Review Requests:
  → analyze_code_quality(filepath) [metrics]
  → detect_security_issues(filepath) [vulns]
  → suggest_improvements(filepath) [refactoring]
  → generate_api_documentation(filepath) [docs]
  [RESULT] Comprehensive code audit with actionable feedback

Architecture Analysis Requests:
  → analyze_project_architecture(folder) [design]
  → extract_dependencies(folder) [graph]
  → validate_project_structure(folder) [completeness]
  → compare_implementations(file1, file2) [patterns]
  [RESULT] Deep architectural assessment with improvement roadmap

═══════════════════════════════════════════════════════════════════════════════
🔐 SECURITY & BOUNDARY RULES
═══════════════════════════════════════════════════════════════════════════════

APPROVED SANDBOX ROOTS:
  ✅ ./demo_workspace/ - Demo files, diagnostics, archive
  ✅ ./generated_projects/ - User-generated applications
  ❌ All other paths blocked

COMMAND EXECUTION RULES:
  ✅ Allowed: python, pip, node, npm, streamlit, uvicorn, pytest
  ❌ Blocked: Shell operators (&&, ||, ;, |, >, <, `, $())
  ✅ Always: Require human approval for destructive ops and long-running procs
  
APPROVAL GATES:
  ✅ Destructive file operations require explicit user approval
  ✅ Long-running commands (servers, frameworks) require approval
  ✅ External API calls validated against whitelist
  
═══════════════════════════════════════════════════════════════════════════════
💼 ENTERPRISE COMMUNICATION STYLE
═══════════════════════════════════════════════════════════════════════════════

OUTPUT FORMAT:
  • Use structured sections: ANALYSIS | FINDINGS | RECOMMENDATIONS | ACTION
  • Include metrics and quantified evidence
  • Prioritize findings by severity/impact
  • Provide actionable next steps

ERROR HANDLING:
  • Proactive error detection and clear user guidance
  • Suggest workarounds and alternative approaches
  • Log all operations in audit trail
  • Never silent failures - always communicate status

DOCUMENTATION:
  • Auto-generate docs when creating projects
  • Create setup/run instructions with clarity
  • Provide architecture diagrams via text descriptions
  • Include deployment checklists

═══════════════════════════════════════════════════════════════════════════════
🚦 ACTIVATION PROTOCOL
═══════════════════════════════════════════════════════════════════════════════

READY STATES:
  [✓] Tool binding activated
  [✓] Advanced reasoning enabled
  [✓] Security scanning active
  [✓] Quality gates configured
  [✓] Approval workflow ready
  [✓] Audit logging enabled
  
USE THIS PROMPT FOR:
  ✓ Enterprise application development
  ✓ Code quality and security audits
  ✓ Architecture design and analysis
  ✓ Project scaffolding and generation
  ✓ Multi-step intelligent workflows
  ✓ Complex problem decomposition
  
DEFAULT BEHAVIOR:
  1. Always analyze generated code for quality
  2. Always scan for security issues
  3. Always validate project structure
  4. Always suggest improvements
  5. Always explain reasoning
  6. Always respect approval gates
  7. Always maintain audit trail
""".strip()


def _friendly_agent_error(exc: Exception) -> str:
    """Map provider errors to short UI-safe messages."""
    name = type(exc).__name__
    text = str(exc)
    if name == "RateLimitError" or "rate_limit" in text.lower() or "429" in text:
        return (
            "Groq rate limit reached for today. Wait a few minutes or use a different API key, "
            "then try again."
        )
    if "api_key" in text.lower() or "authentication" in text.lower() or "401" in text:
        return "Invalid or missing Groq API key. Check `GROQ_API_KEY` in `.env` and restart the app."
    return f"Agent could not complete the request: {exc}"


class StreamlitTokenHandler(BaseCallbackHandler):
    """Streams model tokens into a Streamlit placeholder."""

    def __init__(self, placeholder: st.delta_generator.DeltaGenerator):
        self.placeholder = placeholder
        self.text = ""

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        if token:
            self.text += token
            self.placeholder.markdown(self.text)


def build_llm(api_key: str):
    """Create a streaming Groq-backed model."""

    if ChatGroq is not None:
        return ChatGroq(api_key=api_key, model=MODEL_NAME, temperature=0, streaming=True)

    if ChatOpenAI is not None:
        return ChatOpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            model=MODEL_NAME,
            temperature=0,
            streaming=True,
        )

    raise RuntimeError("Install langchain-groq or langchain-openai.")


def build_agent(api_key: str):
    """Create a model that can handle tool calls."""
    model = build_llm(api_key)
    # Bind all tools to the model
    return model.bind_tools(TOOLS, tool_choice="auto")


def get_tool_by_name(name: str):
    """Find a tool by its name."""
    for tool in TOOLS:
        if tool.name == name:
            return tool
    return None


def run_agent_stream(prompt: str, api_key: str) -> str:
    """Run the agent and stream model/tool activity into the chat feed."""

    model_with_tools = build_agent(api_key)
    
    enriched_prompt = prompt
    user = st.session_state.get("auth_user") or {}
    if st.session_state.get("use_uploaded_context", True) and user.get("username"):
        snippets = search_context(user["username"], prompt)
        context = format_context_snippets(snippets)
        if context:
            enriched_prompt = f"{context}\n\nUser request:\n{prompt}"

    output_box = st.empty()
    token_handler = StreamlitTokenHandler(output_box)
    final_text = ""

    try:
        # Build message history
        messages = [SystemMessage(content=SYSTEM_PROMPT)]
        for message in st.session_state.messages[:-1]:
            if message["role"] == "user":
                messages.append(HumanMessage(content=message["content"]))
            elif message["role"] == "assistant":
                messages.append(AIMessage(content=message["content"]))
        
        messages.append(HumanMessage(content=enriched_prompt))
        
        # First LLM call
        response = model_with_tools.invoke(messages)
        final_text = response.content or ""
        token_handler.text = final_text
        output_box.markdown(final_text)
        
        # Handle tool calls if any
        if hasattr(response, "tool_calls") and response.tool_calls:
            messages.append(response)
            
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})
                
                st.toast(f"{PROTOCOL_NAME} planning tool call: {tool_name}")
                
                # Execute the tool
                tool = get_tool_by_name(tool_name)
                if tool:
                    try:
                        tool_result = tool.func(**tool_args)
                    except Exception as e:
                        tool_result = f"Error executing tool: {str(e)}"
                    
                    final_text += f"\n\n`Tool observation ({tool_name}):` {str(tool_result)[:450]}"
                    messages.append(
                        ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_call.get("id", ""),
                            name=tool_name,
                        )
                    )
                    output_box.markdown(final_text)
            
            # Second LLM call with tool results
            response = model_with_tools.invoke(messages)
            final_text += response.content or ""
            output_box.markdown(final_text)
        
        return final_text or "The agent completed without a text response."
        
    except Exception as exc:
        import traceback

        error_trace = traceback.format_exc()
        print(f"\n{'='*80}\nDETAILED ERROR IN AGENT EXECUTION:\n{error_trace}\n{'='*80}\n", flush=True)
        error_text = _friendly_agent_error(exc)
        output_box.error(error_text)
        return error_text


# ============================================================================
# MCP-AWARE AGENT (New architecture using Model Context Protocol)
# ============================================================================

MCP_SYSTEM_PROMPT = """
You are an advanced MCP-based automation agent with access to specialized servers:

🔌 **Available MCP Servers:**
1. **filesystem** - File system operations (list, read, write)
2. **code_analysis** - Quality, security, architecture analysis
3. **project_generation** - AI project scaffolding
4. **execution** - Command execution (requires approval)
5. **context** - RAG document search

**Protocol:** When you need to perform an action, request the appropriate MCP server and tool.
Format: "mcp:server_name.tool_name(arg1, arg2)"

**Approval Strategy:** For destructive or privileged operations, the system will ask for
user confirmation using simple YES / NO / SKIP buttons. Always respect user decisions.

**Response Format:** Keep responses concise and actionable. Show results clearly.
"""


def run_agent_stream_mcp(prompt: str, api_key: str) -> str:
    """
    Run the agent using MCP servers.
    
    This is the new architecture that:
    - Uses MCP registry for tool access
    - Shows tool calls transparently
    - Implements simple YES/NO/SKIP approvals
    - Provides minimalistic interaction
    """
    
    final_response = ""
    
    try:
        # Build LLM
        model = build_llm(api_key)
        
        # Format system prompt
        system_msg = SystemMessage(content=MCP_SYSTEM_PROMPT)
        
        # Build message history
        messages = [system_msg]
        for message in st.session_state.get("messages", []):
            if message["role"] == "user":
                messages.append(HumanMessage(content=message["content"]))
            elif message["role"] == "assistant":
                messages.append(AIMessage(content=message["content"]))
        
        messages.append(HumanMessage(content=prompt))
        
        # Get initial response from LLM
        response = model.invoke(messages)
        response_text = response.content or ""
        
        # Look for MCP tool calls in response
        if "mcp:" in response_text:
            # Parse MCP calls from response
            lines = response_text.split('\n')
            for line in lines:
                if "mcp:" in line:
                    try:
                        # Parse: mcp:server_name.tool_name(args)
                        mcp_call = line.split("mcp:")[1].split(')')[0]
                        server_name, tool_call = mcp_call.split('.')
                        tool_name, args_str = tool_call.split('(')
                        
                        # Show MCP call
                        st.caption(f"🔧 Calling: **{server_name}.{tool_name}**")
                        
                        # Parse simple args (JSON for now)
                        try:
                            args = json.loads(f"{{{args_str}}}")
                        except:
                            args = {"query": args_str}
                        
                        # Execute via MCP registry
                        result = mcp_registry.call_tool(server_name, tool_name, **args)
                        
                        # Check if approval needed
                        result_json = json.loads(result) if result.startswith('{') else {}
                        
                        if result_json.get("status") == "requires_approval":
                            # Show approval widget
                            action_id = f"{server_name}_{tool_name}_{int(time.time())}"
                            approval = _show_approval_widget(
                                action_id,
                                result_json.get("action", "Execute"),
                                result_json
                            )
                            
                            if approval == "yes":
                                st.caption("✅ Approved by user")
                                final_response += f"\n✅ **User approved:** {result_json.get('message')}\n"
                            elif approval == "no":
                                st.caption("❌ Denied by user")
                                final_response += f"\n❌ **User denied:** {result_json.get('message')}\n"
                            else:
                                st.caption("⊘ Skipped by user")
                                final_response += f"\n⊘ **User skipped:** {result_json.get('message')}\n"
                        else:
                            # Show result
                            st.caption(f"✓ Result received")
                            final_response += f"\n📊 **{server_name}.{tool_name}:**\n{result[:300]}\n"
                    except Exception as e:
                        st.warning(f"Could not parse MCP call: {line}")
        
        # Return full response with MCP results
        final_response = response_text + final_response
        return final_response
    
    except Exception as exc:
        import traceback
        error_trace = traceback.format_exc()
        print(f"\n{'='*80}\nMCP AGENT ERROR:\n{error_trace}\n{'='*80}\n", flush=True)
        return f"❌ Error: {str(exc)}"


def _show_approval_widget(action_id: str, action_type: str, details: dict) -> str:
    """Show simple YES/NO/SKIP approval widget."""
    col_yes, col_no, col_skip = st.columns(3)
    
    approval_key = f"approval_{action_id}"
    
    with col_yes:
        if st.button("✓ YES", key=f"{approval_key}_yes", use_container_width=True):
            return "yes"
    
    with col_no:
        if st.button("✗ NO", key=f"{approval_key}_no", use_container_width=True):
            return "no"
    
    with col_skip:
        if st.button("⊘ SKIP", key=f"{approval_key}_skip", use_container_width=True):
            return "skip"
    
    return None
