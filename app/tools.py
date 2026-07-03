import shutil
import shlex
import subprocess
import time
from pathlib import Path

import streamlit as st
from langchain_core.tools import tool

from app.audit import record_tool_event
from app.config import ARCHIVE_DIR, PROJECTS_DIR, RUN_LOGS_DIR, WORKSPACE_ROOT
from app.project_builder import generate_project
from app.rag import format_context_snippets, search_context
from app.security import resolve_generated_project_path, resolve_workspace_path
from app.workspace import initialize_environment


def split_filenames(filenames_string: str) -> list[str]:
    return [name.strip() for name in filenames_string.split(",") if name.strip()]


def current_username() -> str:
    user = st.session_state.get("auth_user") or {}
    return user.get("username", "local_user")


def _reject_command(command: str) -> str | None:
    blocked_tokens = ["&&", "||", ";", "|", ">", "<", "`", "$("]
    if any(token in command for token in blocked_tokens):
        return "Command rejected because shell operators are not allowed."

    try:
        parts = shlex.split(command, posix=False)
    except ValueError as exc:
        return f"Command rejected because it could not be parsed: {exc}"

    if not parts:
        return "Command rejected because it is empty."

    executable = Path(parts[0]).name.lower()
    allowed = {"python", "python.exe", "py", "py.exe", "pip", "pip.exe", "streamlit", "streamlit.exe", "uvicorn", "uvicorn.exe", "npm", "npm.cmd", "node", "node.exe", "npx", "npx.cmd"}
    if executable not in allowed:
        return f"Command rejected because `{parts[0]}` is not in the allowed local tool list."
    return None


def _is_long_running(command: str) -> bool:
    parts = [part.lower() for part in shlex.split(command, posix=False)]
    return bool(parts and (parts[0] in {"streamlit", "streamlit.exe", "uvicorn", "uvicorn.exe"}))


@tool("list_workspace_files")
def list_workspace_files(dummy: str = "") -> str:
    """List files available inside demo files and generated projects."""

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
    record_tool_event("list_workspace_files", "ALLOWED", "Workspace and generated project inventory completed.")
    return (
        "Demo files in ./demo_workspace/:\n"
        + ("\n".join(f"- {name}" for name in demo_files) or "- none")
        + "\n\nGenerated project files in ./generated_projects/:\n"
        + ("\n".join(f"- {name}" for name in project_files) or "- none")
    )


@tool("inspect_file")
def inspect_file(filename: str) -> str:
    """Read raw text from a file inside ./demo_workspace/."""

    path, violation = resolve_workspace_path(filename)
    if violation:
        record_tool_event("inspect_file", "BLOCKED", violation)
        return violation

    if not path or not path.exists() or not path.is_file():
        record_tool_event("inspect_file", "BLOCKED", f"File not found: {filename}")
        return f"File not found inside ./demo_workspace/: {filename}"

    contents = path.read_text(encoding="utf-8")
    record_tool_event("inspect_file", "ALLOWED", f"Inspected {path.name}.")
    return f"Raw contents of {path.name}:\n\n{contents}"


@tool("create_or_update_file")
def create_or_update_file(relative_path: str, contents: str) -> str:
    """Create or overwrite a UTF-8 text file inside ./generated_projects/."""

    path, violation = resolve_generated_project_path(relative_path)
    if violation:
        record_tool_event("create_or_update_file", "BLOCKED", violation)
        return violation

    if not path:
        record_tool_event("create_or_update_file", "BLOCKED", "Empty path rejected.")
        return "Empty path rejected."

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    record_tool_event("create_or_update_file", "ALLOWED", f"Wrote {path.relative_to(PROJECTS_DIR)}.")
    return f"Saved `generated_projects/{path.relative_to(PROJECTS_DIR)}` ({len(contents)} characters)."


@tool("create_project_from_prompt")
def create_project_from_prompt(project_prompt: str) -> str:
    """Generate a runnable project with folders, files, README, requirements, and VS Code tasks."""

    initialize_environment(reset=False)
    manifest = generate_project(project_prompt, owner=current_username())
    record_tool_event("create_project_from_prompt", "ALLOWED", f"Generated {manifest['project']}.")
    files = "\n".join(f"- {name}" for name in manifest["files"] + ["agent_manifest.json"])
    return (
        f"Generated project `{manifest['project']}` inside `{manifest['path']}`.\n\n"
        f"Files created:\n{files}\n\n"
        f"Project command folder: `{manifest['command_cwd']}`\n"
        f"Setup command: `{manifest['setup_command']}`\n"
        f"Run command: `{manifest['run_command']}`"
    )


@tool("search_uploaded_context")
def search_uploaded_context(query: str) -> str:
    """Search the signed-in user's uploaded documents and image metadata with ChromaDB-backed RAG."""

    snippets = search_context(current_username(), query)
    record_tool_event("search_uploaded_context", "ALLOWED", f"Retrieved {len(snippets)} context snippet(s).")
    return format_context_snippets(snippets) or "No uploaded context matched this query."


def execute_workspace_command(command: str, cwd: str = ".", approved: bool = False) -> str:
    """Run an approved command inside ./generated_projects/ or one of its child folders."""

    rejection = _reject_command(command)
    if rejection:
        record_tool_event("run_workspace_command", "BLOCKED", rejection)
        return rejection

    cwd_path, violation = resolve_generated_project_path(cwd)
    if violation:
        record_tool_event("run_workspace_command", "BLOCKED", violation)
        return violation
    if not cwd_path or not cwd_path.exists() or not cwd_path.is_dir():
        record_tool_event("run_workspace_command", "BLOCKED", f"Working directory not found: {cwd}")
        return f"Working directory not found inside ./generated_projects/: {cwd}"

    if st.session_state.get("require_command_approval", True) and not approved:
        st.session_state.pending_command_action = {"command": command, "cwd": cwd}
        record_tool_event("run_workspace_command", "BLOCKED", "Human approval required before command execution.")
        return "Human approval required. The setup or run command is paused in the UI."

    args = shlex.split(command, posix=False)
    RUN_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RUN_LOGS_DIR / f"command-{int(time.time())}.log"

    if _is_long_running(command):
        log_handle = log_path.open("a", encoding="utf-8")
        try:
            process = subprocess.Popen(
                args,
                cwd=str(cwd_path),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
        finally:
            log_handle.close()
        st.session_state.setdefault("running_processes", []).append(
            {"pid": process.pid, "command": command, "cwd": str(cwd_path), "log": str(log_path)}
        )
        record_tool_event("run_workspace_command", "ALLOWED", f"Started process {process.pid}.")
        return f"Started `{command}` in `{cwd}` as PID {process.pid}. Log: `{log_path}`"

    completed = subprocess.run(
        args,
        cwd=str(cwd_path),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    output = (completed.stdout + "\n" + completed.stderr).strip()
    log_path.write_text(output, encoding="utf-8")
    status = "ALLOWED" if completed.returncode == 0 else "BLOCKED"
    record_tool_event("run_workspace_command", status, f"Exit code {completed.returncode}.")
    return (
        f"Command `{command}` finished with exit code {completed.returncode}.\n"
        f"Log: `{log_path}`\n\n"
        f"{output[:2000]}"
    )


@tool("run_workspace_command")
def run_workspace_command(command: str, cwd: str = ".") -> str:
    """Run an allow-listed setup or app command inside ./generated_projects/ after human approval."""

    return execute_workspace_command(command, cwd=cwd, approved=False)


def archive_files_after_approval(filenames_string: str, approved: bool) -> str:
    """Move files into archive after boundary checks and optional approval."""

    filenames = split_filenames(filenames_string)
    if not filenames:
        record_tool_event("safe_archive_files", "BLOCKED", "No filenames supplied.")
        return "No filenames supplied for archival."

    resolved_paths = []
    for filename in filenames:
        path, violation = resolve_workspace_path(filename)
        if violation:
            record_tool_event("safe_archive_files", "BLOCKED", violation)
            return violation
        if not path or not path.exists() or not path.is_file():
            record_tool_event("safe_archive_files", "BLOCKED", f"File not found: {filename}")
            return f"File not found inside ./demo_workspace/: {filename}"
        resolved_paths.append(path)

    if st.session_state.get("require_human_approval", True) and not approved:
        st.session_state.pending_archive_action = {
            "filenames_string": filenames_string,
            "filenames": filenames,
        }
        record_tool_event(
            "safe_archive_files",
            "BLOCKED",
            "Human-in-the-loop approval required before destructive file move.",
        )
        return "Human approval required. The archive operation is paused in the UI."

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    moved = []
    for source in resolved_paths:
        destination = ARCHIVE_DIR / source.name
        if destination.exists():
            destination = ARCHIVE_DIR / f"{source.stem}-{int(time.time())}{source.suffix}"
        shutil.move(str(source), str(destination))
        moved.append(f"{source.name} -> archive/{destination.name}")

    st.session_state.pending_archive_action = None
    record_tool_event("safe_archive_files", "ALLOWED", f"Archived {len(moved)} file(s).")
    return "Archived files:\n" + "\n".join(f"- {item}" for item in moved)


@tool("safe_archive_files")
def safe_archive_files(filenames_string: str) -> str:
    """Move comma-separated files from ./demo_workspace/ into ./demo_workspace/archive/."""

    return archive_files_after_approval(filenames_string, approved=False)


# ============ ADVANCED INTELLIGENCE TOOLS ============

@tool("analyze_code_quality")
def analyze_code_quality(filepath: str) -> str:
    """Perform static analysis on Python code: complexity, style, maintainability, LOC metrics."""
    
    path, violation = resolve_workspace_path(filepath)
    if violation:
        record_tool_event("analyze_code_quality", "BLOCKED", violation)
        return violation
    
    if not path or not path.exists() or not path.is_file():
        record_tool_event("analyze_code_quality", "BLOCKED", f"File not found: {filepath}")
        return f"File not found: {filepath}"
    
    if not filepath.endswith('.py'):
        record_tool_event("analyze_code_quality", "BLOCKED", "Only Python files supported")
        return "Only Python files (.py) are supported for code quality analysis."
    
    contents = path.read_text(encoding="utf-8")
    lines = contents.split('\n')
    
    import ast
    metrics = {
        "total_lines": len(lines),
        "code_lines": len([l for l in lines if l.strip() and not l.strip().startswith('#')]),
        "comment_lines": len([l for l in lines if l.strip().startswith('#')]),
        "blank_lines": len([l for l in lines if not l.strip()]),
    }
    
    try:
        tree = ast.parse(contents)
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
    
    analysis = f"""
CODE QUALITY ANALYSIS: {path.name}
{'='*50}
Lines of Code:
- Total: {metrics['total_lines']}
- Code: {metrics['code_lines']}
- Comments: {metrics['comment_lines']}
- Blank: {metrics['blank_lines']}
- Comment Ratio: {metrics['comment_lines']/metrics['code_lines']*100:.1f}%

Structure:
- Functions: {metrics['functions']}
- Classes: {metrics['classes']}
- Avg Function Size: {metrics['avg_function_length']} statements
- Avg Cyclomatic Complexity: {metrics['avg_cyclomatic_complexity']:.2f}
- Max Function Complexity: {metrics['max_function_complexity']}

Recommendations:
{_generate_quality_recommendations(metrics)}
"""
    record_tool_event("analyze_code_quality", "ALLOWED", f"Analyzed {path.name}.")
    return analysis.strip()


@tool("detect_security_issues")
def detect_security_issues(filepath: str) -> str:
    """Scan Python code for common security vulnerabilities and anti-patterns."""
    
    path, violation = resolve_workspace_path(filepath)
    if violation:
        record_tool_event("detect_security_issues", "BLOCKED", violation)
        return violation
    
    if not path or not path.exists() or not path.is_file():
        record_tool_event("detect_security_issues", "BLOCKED", f"File not found: {filepath}")
        return f"File not found: {filepath}"
    
    contents = path.read_text(encoding="utf-8")
    issues = []
    
    # Check for common security issues
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
        if pattern in contents:
            issues.append(issue)
    
    if not issues:
        record_tool_event("detect_security_issues", "ALLOWED", "No issues detected.")
        return "✅ No major security issues detected in this file."
    
    result = f"🛡️ SECURITY SCAN: {path.name}\n{'='*50}\n" + "\n".join(f"- {issue}" for issue in issues)
    record_tool_event("detect_security_issues", "ALLOWED", f"Found {len(issues)} potential issue(s).")
    return result


@tool("extract_dependencies")
def extract_dependencies(project_folder: str) -> str:
    """Analyze project dependencies from requirements.txt, package.json, pyproject.toml, etc."""
    
    proj_path, violation = resolve_generated_project_path(project_folder)
    if violation:
        record_tool_event("extract_dependencies", "BLOCKED", violation)
        return violation
    
    if not proj_path or not proj_path.exists() or not proj_path.is_dir():
        record_tool_event("extract_dependencies", "BLOCKED", f"Project folder not found: {project_folder}")
        return f"Project folder not found: {project_folder}"
    
    deps = {}
    
    # Check Python dependencies
    req_file = proj_path / "requirements.txt"
    if req_file.exists():
        reqs = req_file.read_text().strip().split('\n')
        deps['python'] = [r.strip() for r in reqs if r.strip() and not r.startswith('#')]
    
    # Check pyproject.toml
    pyproj = proj_path / "pyproject.toml"
    if pyproj.exists():
        content = pyproj.read_text()
        if 'dependencies' in content:
            deps['python_poetry'] = "Dependencies found in pyproject.toml"
    
    # Check Node dependencies
    pkg_json = proj_path / "package.json"
    if pkg_json.exists():
        try:
            import json
            data = json.loads(pkg_json.read_text())
            deps['nodejs'] = list(data.get('dependencies', {}).keys())
            deps['devDependencies'] = list(data.get('devDependencies', {}).keys())
        except:
            pass
    
    if not deps:
        record_tool_event("extract_dependencies", "ALLOWED", "No dependency files found.")
        return "No dependency files (requirements.txt, package.json, pyproject.toml) found in project."
    
    result = f"📦 DEPENDENCY ANALYSIS: {project_folder}\n{'='*50}\n"
    for lang, packages in deps.items():
        if isinstance(packages, list):
            result += f"\n{lang}:\n"
            for pkg in packages[:10]:
                result += f"  - {pkg}\n"
            if len(packages) > 10:
                result += f"  ... and {len(packages)-10} more\n"
        else:
            result += f"\n{lang}: {packages}\n"
    
    record_tool_event("extract_dependencies", "ALLOWED", f"Analyzed {len(deps)} dependency sources.")
    return result


@tool("suggest_improvements")
def suggest_improvements(filepath: str) -> str:
    """Analyze code and suggest improvements for readability, performance, and maintainability."""
    
    path, violation = resolve_workspace_path(filepath)
    if violation:
        record_tool_event("suggest_improvements", "BLOCKED", violation)
        return violation
    
    if not path or not path.exists() or not path.is_file():
        record_tool_event("suggest_improvements", "BLOCKED", f"File not found: {filepath}")
        return f"File not found: {filepath}"
    
    contents = path.read_text(encoding="utf-8")
    suggestions = []
    
    # Pattern-based suggestions
    if 'import *' in contents:
        suggestions.append("❌ Avoid 'from X import *', specify what you need")
    if '# TODO' in contents or '# FIXME' in contents:
        suggestions.append("⚠️ Contains TODO/FIXME comments - track in issues instead")
    if contents.count('\n\n\n') > 0:
        suggestions.append("🔄 Multiple blank lines found - consolidate for readability")
    if 'try:' in contents and contents.count('except:') > contents.count('except Exception'):
        suggestions.append("🛡️ Use specific exception types instead of bare except:")
    if len(contents) > 50000:
        suggestions.append("📦 File is large (>50KB) - consider breaking into smaller modules")
    if contents.count('def ') > 30:
        suggestions.append("📂 Many functions in one file - consider organizing into classes or modules")
    
    if not suggestions:
        suggestions.append("✅ Code looks well-structured!")
    
    result = f"💡 IMPROVEMENT SUGGESTIONS: {path.name}\n{'='*50}\n" + "\n".join(f"- {s}" for s in suggestions)
    record_tool_event("suggest_improvements", "ALLOWED", "Generated suggestions.")
    return result


@tool("compare_implementations")
def compare_implementations(file1: str, file2: str) -> str:
    """Compare two code files and highlight differences in approach, complexity, and patterns."""
    
    path1, v1 = resolve_workspace_path(file1)
    path2, v2 = resolve_workspace_path(file2)
    
    if v1:
        record_tool_event("compare_implementations", "BLOCKED", v1)
        return v1
    if v2:
        record_tool_event("compare_implementations", "BLOCKED", v2)
        return v2
    
    if not (path1 and path1.exists()) or not (path2 and path2.exists()):
        record_tool_event("compare_implementations", "BLOCKED", "One or both files not found")
        return "One or both files not found."
    
    c1 = path1.read_text(encoding="utf-8")
    c2 = path2.read_text(encoding="utf-8")
    
    import difflib
    diff = difflib.unified_diff(c1.splitlines(), c2.splitlines(), lineterm='', n=1)
    diff_lines = list(diff)
    
    stats = {
        "lines_1": len(c1.splitlines()),
        "lines_2": len(c2.splitlines()),
        "diff_lines": len(diff_lines),
        "funcs_1": c1.count('def '),
        "funcs_2": c2.count('def '),
    }
    
    result = f"""
IMPLEMENTATION COMPARISON
{'='*50}
File 1: {file1} ({stats['lines_1']} lines, {stats['funcs_1']} functions)
File 2: {file2} ({stats['lines_2']} lines, {stats['funcs_2']} functions)

Difference Summary:
- Changed lines: {stats['diff_lines']}
- Line growth: {stats['lines_2'] - stats['lines_1']:+d}
- Function count change: {stats['funcs_2'] - stats['funcs_1']:+d}

Key differences (first 50 lines):
{chr(10).join(diff_lines[:50])}
"""
    record_tool_event("compare_implementations", "ALLOWED", "Compared files.")
    return result.strip()


@tool("validate_project_structure")
def validate_project_structure(project_folder: str) -> str:
    """Check if project has essential files and proper structure."""
    
    proj_path, violation = resolve_generated_project_path(project_folder)
    if violation:
        record_tool_event("validate_project_structure", "BLOCKED", violation)
        return violation
    
    if not proj_path or not proj_path.exists() or not proj_path.is_dir():
        record_tool_event("validate_project_structure", "BLOCKED", f"Project not found: {project_folder}")
        return f"Project folder not found: {project_folder}"
    
    checks = {
        "README.md": proj_path / "README.md",
        "requirements.txt or package.json": (proj_path / "requirements.txt", proj_path / "package.json"),
        "Source code (src/ or app/)": (proj_path / "src", proj_path / "app"),
        "Configuration (.env.example or config)": (proj_path / ".env.example", proj_path / "config"),
        "Tests (test/ or tests/)": (proj_path / "test", proj_path / "tests"),
        "License": proj_path / "LICENSE",
    }
    
    found = []
    missing = []
    
    for name, paths in checks.items():
        paths = paths if isinstance(paths, tuple) else (paths,)
        if any(p.exists() for p in paths):
            found.append(f"✅ {name}")
        else:
            missing.append(f"❌ {name}")
    
    completeness = len(found) / (len(found) + len(missing)) * 100 if (len(found) + len(missing)) > 0 else 0
    
    result = f"""
PROJECT STRUCTURE VALIDATION: {project_folder}
{'='*50}
Completeness: {completeness:.0f}%

Found:
{chr(10).join(found)}

Recommended:
{chr(10).join(missing)}
"""
    record_tool_event("validate_project_structure", "ALLOWED", f"Validation complete ({completeness:.0f}% complete)")
    return result.strip()


@tool("generate_api_documentation")
def generate_api_documentation(filepath: str) -> str:
    """Auto-generate API documentation from Python docstrings and type hints."""
    
    path, violation = resolve_workspace_path(filepath)
    if violation:
        record_tool_event("generate_api_documentation", "BLOCKED", violation)
        return violation
    
    if not path or not path.exists() or not path.is_file():
        record_tool_event("generate_api_documentation", "BLOCKED", f"File not found: {filepath}")
        return f"File not found: {filepath}"
    
    contents = path.read_text(encoding="utf-8")
    
    import ast
    try:
        tree = ast.parse(contents)
    except SyntaxError as e:
        return f"Syntax error: {e}"
    
    docs = f"# API Documentation: {path.name}\n\n"
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            sig = f"{node.name}("
            if node.args.args:
                args = [arg.arg for arg in node.args.args]
                sig += ", ".join(args)
            sig += ")"
            
            docstring = ast.get_docstring(node) or "No documentation"
            docs += f"## {sig}\n{docstring}\n\n"
        
        elif isinstance(node, ast.ClassDef):
            docs += f"### Class: {node.name}\n"
            docstring = ast.get_docstring(node) or "No documentation"
            docs += f"{docstring}\n\n"
    
    record_tool_event("generate_api_documentation", "ALLOWED", "Generated documentation.")
    return docs


@tool("analyze_project_architecture")
def analyze_project_architecture(project_folder: str) -> str:
    """Deep analysis of project architecture: modules, dependencies, design patterns."""
    
    proj_path, violation = resolve_generated_project_path(project_folder)
    if violation:
        record_tool_event("analyze_project_architecture", "BLOCKED", violation)
        return violation
    
    if not proj_path or not proj_path.exists() or not proj_path.is_dir():
        record_tool_event("analyze_project_architecture", "BLOCKED", f"Project not found: {project_folder}")
        return f"Project folder not found: {project_folder}"
    
    analysis = f"🏗️ ARCHITECTURE ANALYSIS: {project_folder}\n{'='*50}\n\n"
    
    # Directory structure
    analysis += "📁 Directory Structure:\n"
    for item in sorted(proj_path.iterdir())[:15]:
        if item.is_dir() and not item.name.startswith('.'):
            files = len(list(item.glob('*')))
            analysis += f"  📂 {item.name}/ ({files} items)\n"
        elif item.is_file() and item.name.endswith(('.py', '.js', '.tsx', '.json', '.yaml')):
            analysis += f"  📄 {item.name}\n"
    
    # Python module analysis
    py_files = list(proj_path.rglob('*.py'))
    if py_files:
        analysis += f"\n🐍 Python Modules: {len(py_files)} files\n"
        for py_file in py_files[:5]:
            rel_path = py_file.relative_to(proj_path)
            analysis += f"  - {rel_path}\n"
        if len(py_files) > 5:
            analysis += f"  ... and {len(py_files)-5} more\n"
    
    # Frontend analysis
    js_files = list(proj_path.rglob('*.{js,tsx,jsx}'))
    if js_files:
        analysis += f"\n⚛️ Frontend: {len(js_files)} JavaScript/React files\n"
    
    # Configuration analysis
    analysis += f"\n⚙️ Configuration Files:\n"
    config_files = ['pyproject.toml', 'setup.py', 'package.json', '.env.example', 'docker-compose.yml', 'Dockerfile']
    for cfg in config_files:
        if (proj_path / cfg).exists():
            analysis += f"  ✅ {cfg}\n"
    
    record_tool_event("analyze_project_architecture", "ALLOWED", "Architecture analysis complete.")
    return analysis


@tool("advanced_search_context")
def advanced_search_context(query: str, num_results: int = 5) -> str:
    """Advanced semantic search with result ranking and context expansion."""
    
    snippets = search_context(current_username(), query, limit=num_results)
    record_tool_event("advanced_search_context", "ALLOWED", f"Retrieved {len(snippets)} results.")
    
    if not snippets:
        return f"No results found for: {query}"
    
    result = f"🔍 ADVANCED SEARCH RESULTS for '{query}'\n{'='*50}\n\n"
    for i, snippet in enumerate(snippets, 1):
        result += f"[{i}] {snippet.get('source', 'Unknown')}\n{snippet.get('text', '')}\n\n"
    
    return result


def _generate_quality_recommendations(metrics):
    """Generate quality improvement recommendations based on metrics."""
    recs = []
    if metrics['comment_lines'] / max(metrics['code_lines'], 1) < 0.1:
        recs.append("  - Add more code comments (currently <10% comment ratio)")
    if metrics['avg_cyclomatic_complexity'] > 5:
        recs.append("  - Reduce function complexity (avg >5, consider refactoring)")
    if metrics.get('functions', 0) > 20:
        recs.append("  - Consider organizing into classes or multiple files")
    if not recs:
        recs.append("  - Code quality is good - maintain current standards")
    return "\n".join(recs)


TOOLS = [
    list_workspace_files,
    inspect_file,
    create_or_update_file,
    create_project_from_prompt,
    search_uploaded_context,
    run_workspace_command,
    safe_archive_files,
    # Advanced Intelligence Tools
    analyze_code_quality,
    detect_security_issues,
    extract_dependencies,
    suggest_improvements,
    compare_implementations,
    validate_project_structure,
    generate_api_documentation,
    analyze_project_architecture,
    advanced_search_context,
]
