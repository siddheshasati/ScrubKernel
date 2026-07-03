import io
import json
import math
import re
import time
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.auth import ensure_user_upload_dir, user_storage_name
from app.config import CHROMA_DIR

try:
    import chromadb
except ImportError:
    chromadb = None


TEXT_SUFFIXES = {".txt", ".md", ".py", ".json", ".csv", ".log", ".html", ".css", ".js", ".ts", ".yml", ".yaml"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
FALLBACK_INDEX = CHROMA_DIR / "fallback_index.json"


class HashEmbeddingFunction:
    """Small deterministic embedding function so Chroma works fully offline."""

    def name(self) -> str:
        return "local-hash-embedding"

    def __call__(self, input: list[str]) -> list[list[float]]:
        return [_embed_text(text) for text in input]

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return self(input)

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self(input)


def _embed_text(text: str, dimensions: int = 64) -> list[float]:
    vector = [0.0] * dimensions
    for token in re.findall(r"[a-zA-Z0-9_]+", text.lower()):
        bucket = int(sha256(token.encode("utf-8")).hexdigest(), 16) % dimensions
        vector[bucket] += 1.0
    length = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / length for value in vector]


def _safe_filename(filename: str) -> str:
    stem = Path(filename).stem or "upload"
    suffix = Path(filename).suffix.lower()
    clean_stem = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in stem)[:80]
    return f"{clean_stem}{suffix}"


def _load_fallback() -> list[dict[str, Any]]:
    if not FALLBACK_INDEX.exists():
        return []
    try:
        return json.loads(FALLBACK_INDEX.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _save_fallback(records: list[dict[str, Any]]) -> None:
    FALLBACK_INDEX.parent.mkdir(parents=True, exist_ok=True)
    FALLBACK_INDEX.write_text(json.dumps(records, indent=2), encoding="utf-8")


def _get_collection():
    if chromadb is None:
        return None
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name="agentic_os_uploads",
        embedding_function=HashEmbeddingFunction(),
        metadata={"description": "User uploaded documents and image metadata for local agent context."},
    )


def chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            split_at = max(text.rfind("\n\n", start, end), text.rfind(". ", start, end))
            if split_at > start + 300:
                end = split_at + 1
        chunks.append(text[start:end].strip())
        start = end
    return [chunk for chunk in chunks if chunk]


def extract_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return content.decode("utf-8", errors="replace")

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except Exception as exc:
            return f"PDF uploaded, but text extraction failed: {exc}"

    if suffix == ".docx":
        try:
            from docx import Document

            document = Document(io.BytesIO(content))
            return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
        except Exception as exc:
            return f"DOCX uploaded, but text extraction failed: {exc}"

    if suffix in IMAGE_SUFFIXES:
        try:
            from PIL import Image

            image = Image.open(io.BytesIO(content))
            return (
                f"Image upload: {filename}\n"
                f"Format: {image.format or suffix.lstrip('.')}\n"
                f"Size: {image.width}x{image.height}px\n"
                "Use this image as visual reference material for the user prompt."
            )
        except Exception:
            return f"Image upload: {filename}. Use this image as visual reference material for the user prompt."

    return f"Uploaded file: {filename}. Binary content was saved but not text-indexed."


def save_and_index_upload(username: str, uploaded_file: Any) -> dict[str, Any]:
    content = uploaded_file.getvalue()
    filename = _safe_filename(uploaded_file.name)
    upload_dir = ensure_user_upload_dir(username)
    target = upload_dir / filename
    if target.exists():
        target = upload_dir / f"{target.stem}-{int(time.time())}{target.suffix}"
    target.write_bytes(content)

    text = extract_text(filename, content)
    chunks = chunk_text(text)
    user_key = user_storage_name(username)
    records = _load_fallback()
    collection = _get_collection()

    ids = []
    for index, chunk in enumerate(chunks or [text]):
        doc_id = f"{user_key}:{target.name}:{index}:{int(time.time() * 1000)}"
        metadata = {
            "username": user_key,
            "source": target.name,
            "path": str(target),
            "chunk": index,
        }
        record = {"id": doc_id, "document": chunk, "metadata": metadata}
        records.append(record)
        ids.append(doc_id)
        if collection is not None and chunk.strip():
            collection.add(ids=[doc_id], documents=[chunk], metadatas=[metadata])

    _save_fallback(records)
    return {
        "filename": target.name,
        "path": str(target),
        "chunks": len(ids),
        "indexed_with": "ChromaDB + local fallback" if collection is not None else "local fallback",
    }


def search_context(username: str, query: str, limit: int = 4) -> list[dict[str, Any]]:
    user_key = user_storage_name(username)
    collection = _get_collection()
    if collection is not None:
        result = collection.query(
            query_texts=[query],
            n_results=limit,
            where={"username": user_key},
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [
            {
                "document": document,
                "metadata": metadata,
                "score": 1.0 / (1.0 + float(distance or 0)),
            }
            for document, metadata, distance in zip(documents, metadatas, distances)
        ]

    query_tokens = set(re.findall(r"[a-zA-Z0-9_]+", query.lower()))
    scored = []
    for record in _load_fallback():
        if record.get("metadata", {}).get("username") != user_key:
            continue
        document = record.get("document", "")
        tokens = set(re.findall(r"[a-zA-Z0-9_]+", document.lower()))
        score = len(query_tokens & tokens) / max(len(query_tokens), 1)
        if score > 0:
            scored.append({**record, "score": score})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def format_context_snippets(snippets: list[dict[str, Any]]) -> str:
    if not snippets:
        return ""
    lines = ["Relevant uploaded context:"]
    for item in snippets:
        metadata = item.get("metadata", {})
        source = metadata.get("source", "upload")
        document = item.get("document", "").strip()
        lines.append(f"\nSource: {source}\n{document[:1200]}")
    return "\n".join(lines)
