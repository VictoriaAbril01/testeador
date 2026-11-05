"""Bounded private artifacts with path confinement and atomic writes."""

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from app.database.config import PROJECT_ROOT
from tester.evidence.screenshots import assess_screenshot

MAX_FILE_BYTES = 1_000_000
MAX_RUN_BYTES = 20_000_000


def evidence_root() -> Path:
    return Path(os.getenv("TESTLAB_EVIDENCE_ROOT", str(PROJECT_ROOT / "artifacts" / "private"))).resolve()


def retention_days() -> int:
    value = int(os.getenv("TESTLAB_EVIDENCE_RETENTION_DAYS", "30"))
    if not 1 <= value <= 365:
        raise ValueError("Evidence retention must be between 1 and 365 days")
    return value


def artifact_path(relative_path: str) -> Path:
    parts = Path(relative_path).parts
    if len(parts) != 2:
        raise ValueError("Invalid evidence path")
    UUID(parts[0])
    UUID(Path(parts[1]).stem)
    if Path(parts[1]).suffix not in {".png", ".json"}:
        raise ValueError("Invalid evidence type")
    root = evidence_root()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Invalid evidence path")
    return path


def save(run_id: UUID, kind: str, data: bytes) -> tuple[str, int, str, datetime] | None:
    if not data or len(data) > MAX_FILE_BYTES:
        return None
    if kind == "screenshot" and assess_screenshot(data).status == "invalid":
        return None
    suffix = ".png" if kind == "screenshot" else ".json"
    relative = f"{run_id}/{uuid4()}{suffix}"
    path = artifact_path(relative)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
    return relative, len(data), hashlib.sha256(data).hexdigest(), datetime.now(timezone.utc) + timedelta(days=retention_days())


def delete(relative_path: str) -> None:
    artifact_path(relative_path).unlink(missing_ok=True)


def read_screenshot_status(relative_path: str) -> dict | None:
    try:
        detail = json.loads(artifact_path(relative_path).read_text(encoding="utf-8"))[0]
        if detail.get("status") not in {"valid", "suspicious", "invalid", "unavailable"}:
            return None
        return {key: detail.get(key) for key in
                ("status", "reason", "page_url", "captured_at", "width", "height")}
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return None


def remove_run_artifacts(run_id: UUID) -> None:
    directory = evidence_root() / str(run_id)
    if not directory.is_dir():
        return
    for entry in directory.iterdir():
        delete(f"{run_id}/{entry.name}")
    directory.rmdir()
