from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from tester.evidence.storage import artifact_path, delete, save
from tester.reproduction.rules import fingerprint, reproduction_steps
from tester.scenarios.types import Observation, StepRecord


def test_reproduction_uses_recorded_actions_and_flags_missing_navigation():
    observed = Observation("http_response", "https://example.test/users", "https://example.test/users", None, "HTTP 500 on document", 500)
    steps = [StepRecord(1, "navigate", "Home", "Home", "https://example.test/", "HTTP 200"),
             StepRecord(2, "navigate", "Users", "Users", "https://example.test/users", "HTTP 500")]
    result = reproduction_steps(observed, steps)
    assert result[0] == "Abrir https://example.test/."
    assert result[1] == "Abrir https://example.test/users."
    assert result[-1].endswith("HTTP 500 on document.")
    missing = reproduction_steps(observed, steps[:1])
    assert any("Falta una navegación registrada" in item for item in missing)


def test_fingerprint_normalizes_urls_and_scopes_module():
    first = Observation("http_response", "https://example.test/users?token=secret", None, None, "HTTP 500 on document")
    second = Observation("http_response", "https://example.test/users#top", None, None, "HTTP 500 on document")
    assert fingerprint("http_5xx", first, "Users") == fingerprint("http_5xx", second, "Users")
    assert fingerprint("http_5xx", first, "Users") != fingerprint("http_5xx", second, "Orders")


def test_private_storage_has_bounded_files_and_rejects_traversal(monkeypatch, tmp_path):
    monkeypatch.setenv("TESTLAB_EVIDENCE_ROOT", str(tmp_path / "private"))
    run_id = uuid4()
    stored = save(run_id, "http_metadata", b"[]")
    assert stored is not None
    relative, size, digest, expires = stored
    assert size == 2 and len(digest) == 64 and expires > datetime.now(timezone.utc)
    assert artifact_path(relative).read_bytes() == b"[]"
    assert save(run_id, "screenshot", b"x" * 1_000_001) is None
    with pytest.raises(ValueError):
        artifact_path("../secrets.json")
    delete(relative)
    assert not artifact_path(relative).exists()
