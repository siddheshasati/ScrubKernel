from pathlib import Path
import os

from dotenv import load_dotenv


APP_TITLE = "ScrubKernel : Agentic OS Automation"
EVENT_NAME = "Agentic OS Automation Event"
MODEL_NAME = "llama-3.1-8b-instant"
PROTOCOL_NAME = "MCP Node"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = (PROJECT_ROOT / "demo_workspace").resolve()
ARCHIVE_DIR = WORKSPACE_ROOT / "archive"
DATA_ROOT = (PROJECT_ROOT / ".app_data").resolve()
USERS_DB_PATH = DATA_ROOT / "users.json"
UPLOADS_DIR = DATA_ROOT / "uploads"
CHROMA_DIR = DATA_ROOT / "chromadb"
RUN_LOGS_DIR = DATA_ROOT / "run_logs"
GENERATED_PROJECTS_DIR = (PROJECT_ROOT / "generated_projects").resolve()
PROJECTS_DIR = GENERATED_PROJECTS_DIR


def load_settings() -> None:
    """Load local secrets and settings from .env."""

    load_dotenv(PROJECT_ROOT / ".env")


def get_groq_api_key() -> str:
    """Return the Groq key from environment variables only."""

    return os.getenv("GROQ_API_KEY", "").strip()
