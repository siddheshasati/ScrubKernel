"""
Model Context Protocol (MCP) Server Implementations.

MCP is a standardized protocol for AI assistants to safely access external tools
and data sources. Each MCP server handles a specific domain of functionality.

This module provides:
- FileSystemMCP: Access to workspace and project files
- CodeAnalysisMCP: Code quality, security, and architecture analysis
- ProjectGenerationMCP: AI-powered project scaffolding
- ExecutionMCP: Safe command execution with approval gates
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Optional
import ast

import streamlit as st
from app.config import PROJECTS_DIR, WORKSPACE_ROOT, ARCHIVE_DIR
from app.audit import record_tool_event
from app.security import resolve_workspace_path, resolve_generated_project_path
from app.project_builder import generate_project
from app.rag import search_context, format_context_snippets


class MCPServer:
    """Base MCP server implementation."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.tools: dict[str, Callable] = {}

    def register_tool(self, name: str, func: Callable, description: str):
        """Register a tool with this MCP server."""
        self.tools[name] = {"func": func, "description": description}

    def call_tool(self, tool_name: str, **kwargs) -> str:
        """Call a tool on this MCP server."""
        if tool_name not in self.tools:
            return f"Tool '{tool_name}' not found in {self.name}."
        
        try:
            result = self.tools[tool_name]["func"](**kwargs)
            return result
        except Exception as e:
            return f"Error in {self.name}/{tool_name}: {str(e)}"

    def list_tools(self) -> list[dict]:
        """List all tools in this MCP server."""
        return [
            {"name": name, "description": data["description"]}
            for name, data in self.tools.items()
        ]


# ============================================================================
# 1. FILE SYSTEM MCP SERVER
# ============================================================================

class FileSystemMCP(MCPServer):
    """MCP server for safe file system operations within approved sandboxes."""

    def __init__(self):
        super().__init__(
            "filesystem",
            "Safe file system access to demo_workspace and generated_projects"
        )
        
        self.register_tool(
            "list_files",
            self._list_files,
            "List all files in workspace and projects"
        )
        self.register_tool(
            "read_file",
            self._read_file,
            "Read content from a file"
        )
        self.register_tool(
            "write_file",
            self._write_file,
            "Write or create a file"
        )
        self.register_tool(
            "delete_file",
            self._delete_file,
            "Delete a file (requires approval)"
        )

    def _list_files(self) -> str:
        """List workspace and project files."""
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
        record_tool_event("filesystem.list_files", "ALLOWED", "Listed files.")
        return json.dumps({
            "demo_workspace": demo_files[:50],
            "generated_projects": project_files[:50],
            "demo_count": len(demo_files),
            "project_count": len(project_files)
        }, indent=2)

    def _read_file(self, filepath: str) -> str:
        """Read a file from approved sandbox."""
        path, violation = resolve_workspace_path(filepath)
        if violation:
            record_tool_event("filesystem.read_file", "BLOCKED", violation)
            return json.dumps({"error": violation})
        
        if not path or not path.exists():
            return json.dumps({"error": f"File not found: {filepath}"})
        
        content = path.read_text(encoding="utf-8")
        record_tool_event("filesystem.read_file", "ALLOWED", f"Read {path.name}")
        return json.dumps({
            "file": str(path.relative_to(WORKSPACE_ROOT)),
            "size": len(content),
            "preview": content[:500],
            "full_content": content
        })

    def _write_file(self, filepath: str, content: str) -> str:
        """Write to a file in generated_projects."""
        path, violation = resolve_generated_project_path(filepath)
        if violation:
            record_tool_event("filesystem.write_file", "BLOCKED", violation)
            return json.dumps({"error": violation})
        
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        record_tool_event("filesystem.write_file", "ALLOWED", f"Wrote {path.name}")
        return json.dumps({
            "status": "success",
            "file": str(path.relative_to(PROJECTS_DIR)),
            "size": len(content)
        })

    def _delete_file(self, filepath: str) -> str:
        """Delete a file (requires human approval via UI)."""
        return json.dumps({
            "status": "requires_approval",
            "action": "delete",
            "file": filepath,
            "message": "Deletion requires human approval"
        })


# ============================================================================
# 2. CODE ANALYSIS MCP SERVER
# ============================================================================

class CodeAnalysisMCP(MCPServer):
    """MCP server for code quality, security, and architecture analysis."""

    def __init__(self):
        super().__init__(
            "code_analysis",
            "Advanced code quality, security, and architecture analysis"
        )
        
        self.register_tool(
            "analyze_quality",
            self._analyze_quality,
            "Analyze code quality metrics"
        )
        self.register_tool(
            "detect_security",
            self._detect_security,
            "Detect security vulnerabilities"
        )
        self.register_tool(
            "analyze_architecture",
            self._analyze_architecture,
            "Analyze project architecture"
        )

    def _analyze_quality(self, filepath: str) -> str:
        """Analyze code quality of a Python file."""
        path, violation = resolve_workspace_path(filepath)
        if violation:
            return json.dumps({"error": violation})
        
        if not path or not path.exists():
            return json.dumps({"error": f"File not found: {filepath}"})
        
        contents = path.read_text(encoding="utf-8")
        lines = contents.split('\n')
        
        try:
            tree = ast.parse(contents)
            functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        except SyntaxError:
            return json.dumps({"error": "Syntax error in file"})
        
        metrics = {
            "total_lines": len(lines),
            "code_lines": len([l for l in lines if l.strip() and not l.strip().startswith('#')]),
            "functions": len(functions),
            "classes": len(classes),
            "complexity": sum(1 for n in ast.walk(tree) if isinstance(n, (ast.If, ast.For, ast.While))),
        }
        
        record_tool_event("code_analysis.analyze_quality", "ALLOWED", "Quality analyzed.")
        return json.dumps(metrics, indent=2)

    def _detect_security(self, filepath: str) -> str:
        """Detect security issues in code."""
        path, violation = resolve_workspace_path(filepath)
        if violation:
            return json.dumps({"error": violation})
        
        if not path or not path.exists():
            return json.dumps({"error": f"File not found: {filepath}"})
        
        contents = path.read_text(encoding="utf-8")
        issues = []
        
        patterns = {
            "exec(": "CRITICAL: Code execution vulnerability",
            "eval(": "CRITICAL: Code evaluation vulnerability",
            "pickle.loads": "CRITICAL: Deserialization vulnerability",
            "password": "WARNING: Possible hardcoded password",
            "api_key": "WARNING: Possible hardcoded API key",
        }
        
        for pattern, severity in patterns.items():
            if pattern in contents:
                issues.append(severity)
        
        record_tool_event("code_analysis.detect_security", "ALLOWED", f"Found {len(issues)} issues")
        return json.dumps({"issues": issues, "count": len(issues)}, indent=2)

    def _analyze_architecture(self, project_path: str) -> str:
        """Analyze project architecture."""
        proj_path, violation = resolve_generated_project_path(project_path)
        if violation:
            return json.dumps({"error": violation})
        
        if not proj_path or not proj_path.exists():
            return json.dumps({"error": f"Project not found: {project_path}"})
        
        py_files = list(proj_path.rglob("*.py"))
        config_files = [f for f in proj_path.iterdir() if f.name in ["pyproject.toml", "package.json", "Dockerfile"]]
        
        record_tool_event("code_analysis.analyze_architecture", "ALLOWED", "Architecture analyzed.")
        return json.dumps({
            "python_modules": len(py_files),
            "config_files": len(config_files),
            "has_tests": len(list(proj_path.rglob("test_*.py"))) > 0,
            "has_docs": (proj_path / "README.md").exists(),
        }, indent=2)


# ============================================================================
# 3. PROJECT GENERATION MCP SERVER
# ============================================================================

class ProjectGenerationMCP(MCPServer):
    """MCP server for AI-powered project generation."""

    def __init__(self):
        super().__init__(
            "project_generation",
            "Generate complete project structures with AI"
        )
        
        self.register_tool(
            "create_project",
            self._create_project,
            "Generate a new project from description"
        )
        self.register_tool(
            "validate_structure",
            self._validate_structure,
            "Validate project completeness"
        )

    def _create_project(self, description: str) -> str:
        """Generate a new project."""
        user = st.session_state.get("auth_user") or {}
        username = user.get("username", "local_user")
        
        manifest = generate_project(description, owner=username)
        record_tool_event("project_generation.create_project", "ALLOWED", f"Generated {manifest['project']}")
        
        return json.dumps({
            "project": manifest['project'],
            "path": manifest['path'],
            "files": manifest['files'],
            "setup_command": manifest['setup_command'],
            "run_command": manifest['run_command'],
        }, indent=2)

    def _validate_structure(self, project_path: str) -> str:
        """Validate project structure."""
        proj_path, violation = resolve_generated_project_path(project_path)
        if violation:
            return json.dumps({"error": violation})
        
        checks = {
            "has_readme": (proj_path / "README.md").exists(),
            "has_requirements": (proj_path / "requirements.txt").exists(),
            "has_src": (proj_path / "src").exists(),
            "has_tests": (proj_path / "tests").exists() or (proj_path / "test").exists(),
        }
        
        completeness = sum(checks.values()) / len(checks) * 100
        record_tool_event("project_generation.validate_structure", "ALLOWED", "Validated structure")
        
        return json.dumps({
            "checks": checks,
            "completeness_percent": completeness,
        }, indent=2)


# ============================================================================
# 4. EXECUTION MCP SERVER
# ============================================================================

class ExecutionMCP(MCPServer):
    """MCP server for safe command execution."""

    def __init__(self):
        super().__init__(
            "execution",
            "Execute approved commands with safety gates"
        )
        
        self.register_tool(
            "execute_command",
            self._execute_command,
            "Execute a command (requires approval)"
        )

    def _execute_command(self, command: str, cwd: str = ".") -> str:
        """Execute a command."""
        return json.dumps({
            "status": "requires_approval",
            "command": command,
            "cwd": cwd,
            "message": "Command execution requires human approval"
        })


# ============================================================================
# 5. RAG/CONTEXT MCP SERVER
# ============================================================================

class ContextMCP(MCPServer):
    """MCP server for RAG (Retrieval-Augmented Generation)."""

    def __init__(self):
        super().__init__(
            "context",
            "Search and retrieve uploaded documents"
        )
        
        self.register_tool(
            "search",
            self._search,
            "Search uploaded documents"
        )

    def _search(self, query: str, limit: int = 5) -> str:
        """Search uploaded context."""
        user = st.session_state.get("auth_user") or {}
        username = user.get("username", "local_user")
        
        snippets = search_context(username, query, limit=limit)
        record_tool_event("context.search", "ALLOWED", f"Found {len(snippets)} results")
        
        return json.dumps({
            "query": query,
            "results_count": len(snippets),
            "results": [
                {
                    "source": s.get("source", "unknown"),
                    "text": s.get("text", "")[:200],
                }
                for s in snippets
            ]
        }, indent=2)


# ============================================================================
# MCP SERVER REGISTRY
# ============================================================================

class MCPRegistry:
    """Registry and router for all MCP servers."""

    def __init__(self):
        self.servers: dict[str, MCPServer] = {
            "filesystem": FileSystemMCP(),
            "code_analysis": CodeAnalysisMCP(),
            "project_generation": ProjectGenerationMCP(),
            "execution": ExecutionMCP(),
            "context": ContextMCP(),
        }

    def call_tool(self, server_name: str, tool_name: str, **kwargs) -> str:
        """Call a tool on a specific MCP server."""
        if server_name not in self.servers:
            return json.dumps({"error": f"Server '{server_name}' not found"})
        
        server = self.servers[server_name]
        return server.call_tool(tool_name, **kwargs)

    def list_servers(self) -> list[dict]:
        """List all available servers and their tools."""
        return [
            {
                "name": name,
                "description": server.description,
                "tools": server.list_tools(),
            }
            for name, server in self.servers.items()
        ]

    def get_tools_for_agent(self) -> list[dict]:
        """Get all tools formatted for agent binding."""
        tools = []
        for server_name, server in self.servers.items():
            for tool_name, tool_data in server.tools.items():
                tools.append({
                    "name": f"{server_name}.{tool_name}",
                    "description": tool_data["description"],
                    "server": server_name,
                    "tool": tool_name,
                })
        return tools


# Global registry instance
mcp_registry = MCPRegistry()
