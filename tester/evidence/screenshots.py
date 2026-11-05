"""Validate private PNG screenshots without exposing page content."""

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO

from PIL import Image, ImageStat, UnidentifiedImageError

MAX_SCREENSHOT_BYTES = 1_000_000


@dataclass(frozen=True)
class ScreenshotAssessment:
    status: str  # valid, suspicious, invalid
    reason: str
    width: int = 0
    height: int = 0


def assess_screenshot(data: bytes) -> ScreenshotAssessment:
    if not data or len(data) > MAX_SCREENSHOT_BYTES:
        return ScreenshotAssessment("invalid", "empty_or_oversized")
    try:
        with Image.open(BytesIO(data)) as header:
            header.verify()
        if not data.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82"):
            return ScreenshotAssessment("invalid", "unreadable_png")
        with Image.open(BytesIO(data)) as image:
            if image.format != "PNG" or image.width < 32 or image.height < 32 or image.width > 10000 or image.height > 10000:
                return ScreenshotAssessment("invalid", "invalid_format_or_dimensions")
            width, height = image.size
            image.load()  # Reject truncated or corrupt IDAT, not just the PNG header.
            sample = image.convert("RGB")
            sample.thumbnail((128, 128))
            stat = ImageStat.Stat(sample)
            extrema = sample.getextrema()
            if max(stat.stddev) < 4 or all(low >= 245 for low, _ in extrema):
                return ScreenshotAssessment("suspicious", "uniform_or_nearly_white", width, height)
            return ScreenshotAssessment("valid", "visual_content_detected", width, height)
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        return ScreenshotAssessment("invalid", "unreadable_png")


# Keep the shape of headings and controls visible while withholding every text glyph.
# Media and editable regions can contain unknown secrets, so they remain hidden.
REDACTION_STYLE = """
    *, *::before, *::after { color: transparent !important; text-shadow: none !important;
      text-decoration-color: transparent !important; -webkit-text-fill-color: transparent !important;
      background-image: none !important; border-image: none !important; }
    h1, h2, h3, h4, h5, h6, p, li, a, button, label, td, th {
      background-color: #dbe7f5 !important; border-radius: 3px !important;
    }
    input, textarea, select, [contenteditable], img, svg, canvas, video, iframe,
    [data-sensitive], [data-private], [aria-label*="password" i] {
      visibility: hidden !important;
    }
"""


async def capture_page(page, *, timeout_ms: int) -> tuple[bytes | None, dict]:
    """Capture the current page after observable rendering, with bounded waiting."""
    from playwright.async_api import Error as PlaywrightError
    captured_at = datetime.now(timezone.utc).isoformat()
    try:
        # A deferred SPA must expose a visible landmark before capture. Pages with
        # no landmark still get a bounded best-effort capture after the timeout.
        try:
            await page.wait_for_function("""() => document.readyState !== 'loading' &&
                document.fonts.status === 'loaded' &&
                [...document.querySelectorAll('main,article,h1,h2,[role="main"]')]
                  .some(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 })""",
                timeout=min(timeout_ms, 2500))
        except PlaywrightError:
            pass
        data = await page.screenshot(scale="css", animations="disabled",
                                     timeout=min(timeout_ms, 3000), style=REDACTION_STYLE)
    except PlaywrightError:
        return None, {"status": "unavailable", "reason": "capture_failed", "captured_at": captured_at}
    assessment = assess_screenshot(data)
    detail = {"status": assessment.status, "reason": assessment.reason,
              "width": assessment.width, "height": assessment.height, "captured_at": captured_at}
    return (data if assessment.status != "invalid" else None), detail
