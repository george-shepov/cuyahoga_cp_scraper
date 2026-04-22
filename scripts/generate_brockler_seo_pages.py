#!/usr/bin/env python3
"""Generate static SEO pages from backend page registry for BrocklerLaw deploy."""

from __future__ import annotations

import html
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.page_registry import PAGE_REGISTRY  # noqa: E402

OUTPUT_ROOT = REPO_ROOT / "docs" / "BROcklerLaw" / "seo"


def _h(value: str) -> str:
    return html.escape(value, quote=True)


def _normalize_href(href: str | None) -> str:
    if href is None:
        return "#"
    if href == "/brocklerlaw":
        return "../../index.html"
    if href.startswith("/brocklerlaw/"):
        trimmed = href.removeprefix("/brocklerlaw/")
        if trimmed in {"", "/"}:
            return "../../index.html"
        if trimmed == "seo":
            return "../index.html"
        if trimmed.startswith("seo/"):
            target = trimmed.removeprefix("seo/").strip("/")
            return f"../{target}/"
        return f"../../{trimmed}"
    return href


def _page_html(slug: str) -> str:
    page = PAGE_REGISTRY[slug]
    related_links = "\n".join(
        f'            <li><a href="{_h(_normalize_href(path))}">{_h(path)}</a></li>'
        for path in page.related_routes
    ) or "            <li>No related routes yet.</li>"

    sections_html = []
    for section in page.sections:
        bullets = "\n".join(f"              <li>{_h(item)}</li>" for item in section.bullets)
        sections_html.append(
            """
        <article class="card section-card">
          <h2>{heading}</h2>
          <p>{body}</p>
          <ul>
{bullets}
          </ul>
        </article>
""".format(heading=_h(section.heading), body=_h(section.body), bullets=bullets)
        )

    faq_html = "\n".join(
        """
        <details class="card faq-item">
          <summary>{question}</summary>
          <p>{answer}</p>
        </details>
""".format(question=_h(item.question), answer=_h(item.answer))
        for item in page.faq
    )

    secondary = ""
    if page.cta.secondary_label and page.cta.secondary_href:
        secondary = (
            f'<a class="btn btn-secondary" href="{_h(_normalize_href(page.cta.secondary_href))}">' \
            f"{_h(page.cta.secondary_label)}</a>"
        )

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>{_h(page.title)}</title>
  <meta name=\"description\" content=\"{_h(page.meta_description)}\">
  <meta name=\"robots\" content=\"index,follow\">
  <link rel=\"canonical\" href=\"https://prosecutordefense.com/brocklerlaw/seo/{_h(slug)}/\">
  <style>
    :root {{
      --bg: #f5efe4;
      --ink: #1b1e24;
      --brand: #b86633;
      --card: #ffffff;
      --line: #ddd0bc;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "Avenir Next", "Segoe UI", sans-serif; color: var(--ink); background: linear-gradient(180deg,#f8f2e8,#f1e6d6); }}
    .wrap {{ width: min(960px, calc(100% - 28px)); margin: 0 auto; padding: 20px 0 40px; }}
    .top {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; font-size: 0.92rem; }}
    .top a {{ color: var(--brand); text-decoration: none; font-weight: 700; }}
    h1 {{ font-family: "Baskerville", "Palatino Linotype", serif; font-size: clamp(2rem, 5vw, 3.4rem); margin: 16px 0 10px; }}
    h2 {{ font-family: "Baskerville", "Palatino Linotype", serif; margin: 0 0 8px; }}
    p {{ line-height: 1.65; }}
    .intro {{ margin-bottom: 18px; }}
    .grid {{ display: grid; gap: 14px; }}
    .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 18px; padding: 18px; box-shadow: 0 8px 24px rgba(0,0,0,0.06); }}
    ul {{ margin: 10px 0 0 18px; padding: 0; }}
    .cta {{ margin-top: 16px; }}
    .btn {{ display: inline-block; padding: 11px 16px; border-radius: 999px; text-decoration: none; font-weight: 700; margin-right: 10px; margin-top: 8px; }}
    .btn-primary {{ background: var(--brand); color: #fff; }}
    .btn-secondary {{ border: 1px solid var(--line); color: var(--ink); background: #fff; }}
    details summary {{ cursor: pointer; font-weight: 700; }}
    .related li a {{ color: var(--brand); }}
  </style>
</head>
<body>
  <main class=\"wrap\">
    <div class=\"top\">
      <a href=\"../../index.html\">Back to main site</a>
      <a href=\"../index.html\">All SEO pages</a>
    </div>

    <h1>{_h(page.h1)}</h1>
    <p class=\"intro\">{_h(page.intro)}</p>

    <section class=\"grid\">
{''.join(sections_html)}
    </section>

    <section class=\"cta card\">
      <h2>{_h(page.cta.heading)}</h2>
      <p>{_h(page.cta.body)}</p>
      <a class=\"btn btn-primary\" href=\"{_h(_normalize_href(page.cta.primary_href))}\">{_h(page.cta.primary_label)}</a>
      {secondary}
    </section>

    <section class=\"grid\" aria-label=\"Frequently asked questions\">
      <h2>Frequently asked questions</h2>
{faq_html}
    </section>

    <section class=\"card related\">
      <h2>Related routes</h2>
      <ul>
{related_links}
      </ul>
    </section>
  </main>
</body>
</html>
"""


def _hub_html(slugs: list[str]) -> str:
    links = "\n".join(
        f'      <li><a href="./{_h(slug)}/">{_h(PAGE_REGISTRY[slug].title)}</a></li>'
        for slug in slugs
    )
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>Brockler Law SEO Pages</title>
  <meta name=\"description\" content=\"SEO landing pages for Cleveland OVI and traffic-defense topics.\">
  <meta name=\"robots\" content=\"index,follow\">
  <style>
    body {{ margin: 0; font-family: "Avenir Next", "Segoe UI", sans-serif; background: #f5efe4; color: #1b1e24; }}
    main {{ width: min(920px, calc(100% - 28px)); margin: 0 auto; padding: 28px 0 38px; }}
    h1 {{ font-family: "Baskerville", "Palatino Linotype", serif; font-size: clamp(2rem, 4.8vw, 3rem); margin: 8px 0 10px; }}
    ul {{ background: #fff; border: 1px solid #ddd0bc; border-radius: 16px; padding: 16px 20px; }}
    li {{ margin: 8px 0; }}
    a {{ color: #b86633; text-decoration: none; }}
  </style>
</head>
<body>
  <main>
    <a href=\"../index.html\">Back to main site</a>
    <h1>SEO landing pages</h1>
    <p>Published topic pages currently generated from the backend page registry.</p>
    <ul>
{links}
    </ul>
  </main>
</body>
</html>
"""


def main() -> None:
    slugs = sorted(PAGE_REGISTRY.keys())
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    for slug in slugs:
        page_dir = OUTPUT_ROOT / slug
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "index.html").write_text(_page_html(slug), encoding="utf-8")

    (OUTPUT_ROOT / "index.html").write_text(_hub_html(slugs), encoding="utf-8")

    print(f"Generated {len(slugs)} SEO pages in {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
