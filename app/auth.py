import hashlib
import hmac
import json
import secrets
from datetime import datetime
from pathlib import Path

from app.config import USERS_DB_PATH


def _load_users() -> dict:
    if not USERS_DB_PATH.exists():
        return {"users": {}}
    try:
        return json.loads(USERS_DB_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"users": {}}


def _save_users(data: dict) -> None:
    USERS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    USERS_DB_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _normalize_username(username: str) -> str:
    return "".join(char for char in username.strip().lower() if char.isalnum() or char in ("_", "-", "."))


def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 160_000)
    return digest.hex()


def user_storage_name(username: str) -> str:
    normalized = _normalize_username(username)
    return normalized or "guest"


def create_account(username: str, password: str, display_name: str = "") -> tuple[bool, str]:
    username = _normalize_username(username)
    if len(username) < 3:
        return False, "Use at least 3 characters for the username."
    if len(password) < 8:
        return False, "Use at least 8 characters for the password."

    data = _load_users()
    if username in data["users"]:
        return False, "That username already exists."

    salt = secrets.token_hex(16)
    data["users"][username] = {
        "display_name": display_name.strip() or username,
        "salt": salt,
        "password_hash": _hash_password(password, salt),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    _save_users(data)
    return True, "Account created. You are signed in."


def authenticate(username: str, password: str) -> tuple[bool, str, dict | None]:
    username = _normalize_username(username)
    data = _load_users()
    user = data["users"].get(username)
    if not user:
        return False, "Username or password is incorrect.", None

    expected = user.get("password_hash", "")
    actual = _hash_password(password, user.get("salt", ""))
    if not hmac.compare_digest(expected, actual):
        return False, "Username or password is incorrect.", None

    return True, "Signed in.", {"username": username, "display_name": user.get("display_name", username)}


def ensure_user_upload_dir(username: str) -> Path:
    from app.config import UPLOADS_DIR

    path = UPLOADS_DIR / user_storage_name(username)
    path.mkdir(parents=True, exist_ok=True)
    return path
