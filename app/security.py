from pathlib import Path

from app.config import PROJECTS_DIR, PROJECT_ROOT, WORKSPACE_ROOT


def security_boundary_violation() -> str:
    return "Security Boundary Violation Check Intercepted"


def resolve_workspace_path(input_path: str) -> tuple[Path | None, str | None]:
    """Allow only relative paths that resolve inside ./demo_workspace/."""

    raw = (input_path or "").strip().strip('"').strip("'")
    if not raw:
        return None, "Empty filename rejected by MCP boundary."

    candidate = Path(raw)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        return None, security_boundary_violation()

    resolved = (WORKSPACE_ROOT / candidate).resolve()
    try:
        resolved.relative_to(WORKSPACE_ROOT)
    except ValueError:
        return None, security_boundary_violation()

    return resolved, None


def resolve_generated_project_path(input_path: str) -> tuple[Path | None, str | None]:
    """Allow only paths inside ./generated_projects/ in the current workspace."""

    raw = (input_path or "").strip().strip('"').strip("'")
    if not raw:
        return None, "Empty path rejected by project boundary."

    candidate = Path(raw)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        return None, security_boundary_violation()

    if candidate.parts and candidate.parts[0] == PROJECTS_DIR.name:
        resolved = (PROJECT_ROOT / candidate).resolve()
    else:
        resolved = (PROJECTS_DIR / candidate).resolve()

    try:
        resolved.relative_to(PROJECTS_DIR)
    except ValueError:
        return None, security_boundary_violation()

    return resolved, None
