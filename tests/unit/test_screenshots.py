"""PNG validity and conservative visual quality classification."""

from io import BytesIO
from uuid import uuid4

from PIL import Image

from tester.evidence.screenshots import assess_screenshot
from tester.evidence.storage import save


def png(color: str) -> bytes:
    output = BytesIO()
    Image.new("RGB", (120, 80), color).save(output, format="PNG")
    return output.getvalue()


def test_empty_corrupt_and_wrong_format_are_invalid(monkeypatch, tmp_path):
    monkeypatch.setenv("TESTLAB_EVIDENCE_ROOT", str(tmp_path))
    for data in (b"", b"not a png", png("red")[:-12]):
        assert assess_screenshot(data).status == "invalid"
        assert save(uuid4(), "screenshot", data) is None
    output = BytesIO()
    Image.new("RGB", (120, 80), "red").save(output, format="JPEG")
    assert assess_screenshot(output.getvalue()).status == "invalid"


def test_uniform_white_page_is_suspicious_but_preserved(monkeypatch, tmp_path):
    monkeypatch.setenv("TESTLAB_EVIDENCE_ROOT", str(tmp_path))
    data = png("white")
    result = assess_screenshot(data)
    assert (result.status, result.width, result.height) == ("suspicious", 120, 80)
    assert save(uuid4(), "screenshot", data) is not None
