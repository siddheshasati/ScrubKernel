import shutil

from app.config import ARCHIVE_DIR, CHROMA_DIR, DATA_ROOT, PROJECTS_DIR, RUN_LOGS_DIR, UPLOADS_DIR, WORKSPACE_ROOT
from app.sample_data import SAMPLE_FILES


def initialize_environment(reset: bool = False) -> None:
    """Create ./demo_workspace/ and seed the three demo files."""

    if reset and WORKSPACE_ROOT.exists():
        if WORKSPACE_ROOT.name != "demo_workspace":
            raise RuntimeError("Refusing to reset an unexpected workspace path.")
        shutil.rmtree(WORKSPACE_ROOT)

    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    RUN_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    for filename, contents in SAMPLE_FILES.items():
        target = WORKSPACE_ROOT / filename
        if reset or not target.exists():
            target.write_text(contents, encoding="utf-8")
