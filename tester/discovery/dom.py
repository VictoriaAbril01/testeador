"""Read-only DOM inventory. Never reads input values or clicks discovered controls."""

from urllib.parse import urlsplit

from playwright.async_api import Page
from tester.blackbox.policy import clean_url
from tester.scenarios.types import Element, PageRecord


_INVENTORY = r"""() => {
  const visible = (el) => !!(el.getClientRects().length);
  const label = (el) => (el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').trim().slice(0, 160);
  const selector = (el) => {
    for (const attr of ['data-testid', 'data-test', 'id', 'name']) {
      const value = el.getAttribute(attr);
      if (value) return attr === 'id' ? `#${CSS.escape(value)}` : `[${attr}="${CSS.escape(value)}"]`;
    }
    return null;
  };
  const nodes = Array.from(document.querySelectorAll('a[href], form, button, input, select, textarea, label')).filter(visible).slice(0, 300);
  const elements = nodes.map((el) => ({
    kind: el.tagName.toLowerCase(),
    text: label(el) || null,
    selector: selector(el),
    href: el.tagName.toLowerCase() === 'a' ? el.href : null
  }));
  const headings = Array.from(document.querySelectorAll('h1,h2,h3')).filter(visible).map(label).filter(Boolean).slice(0, 30);
  const menus = Array.from(document.querySelectorAll('nav,[role="navigation"]')).filter(visible).map(label).filter(Boolean).slice(0, 20);
  const module = document.querySelector('[data-module]')?.getAttribute('data-module')?.trim().slice(0, 200) || null;
  return { title: document.title?.trim().slice(0, 500) || null, headings, menus, elements, module };
}"""


async def inspect_page(page: Page, *, url: str, depth: int, navigation_ms: int | None) -> PageRecord:
    raw = await page.evaluate(_INVENTORY)
    return PageRecord(
        url=url,
        title=raw["title"],
        module=raw["module"],
        depth=depth,
        navigation_ms=navigation_ms,
        headings=tuple(raw["headings"]),
        menus=tuple(raw["menus"]),
        elements=tuple(Element(
            kind=item["kind"], text=item["text"], selector=item["selector"],
            href=clean_url(item["href"]) if item["href"] and item["href"].startswith(("http://", "https://")) and not urlsplit(item["href"]).query else None,
        ) for item in raw["elements"]),
    )
