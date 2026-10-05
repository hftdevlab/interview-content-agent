"""Build a reader-facing HTML/PDF preview of the system-design track.

The existing ReportLab guide builder renders a small Markdown subset. This
preview exists to judge *reading experience* -- paragraph rhythm, callouts,
tables, and figures -- the way a reader will see it. It follows the handbook's
approach: Markdown -> self-contained HTML (figures inlined) -> PDF via headless
Chromium.

Requirements: pandoc, plus Playwright with Chromium for the PDF step
(``pip install playwright && playwright install chromium``). Without
Playwright the HTML is still written.

Usage:
    python -m tools.build_sd_preview                 # all system-design packages in track order
    python -m tools.build_sd_preview --id sd-news-feed
    python -m tools.build_sd_preview --html-only
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from tools.validate import load_data

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "generated" / "pdf-preview"
GUIDE_TITLE = "THE HFT ENGINEER INTERVIEW GUIDE"
TRACK_TITLE = "System Design Track"

CSS = r"""
@page { size: Letter; margin: 0.85in 0.9in 0.8in 0.9in; }
:root {
  --ink:#1f2328; --muted:#6b7280; --rule:#d5dae1; --fill:#f6f7f9;
  --accent:#1a6fb5; --accentFill:#eef5fc; --warn:#b5501a; --warnFill:#fdf1e8;
  --ok:#2f7a4f; --okFill:#eef7f1;
}
html { font-size: 10.6pt; }
body { font-family: Charter, 'Bitstream Charter', 'DejaVu Serif', Georgia, serif;
       color: var(--ink); line-height: 1.52; margin: 0; }
h1, h2, h3, h4, .eyebrow, th, figcaption, .callout strong:first-child, .track p {
  font-family: Inter, 'Helvetica Neue', Arial, sans-serif; }
h1 { font-size: 23pt; line-height: 1.15; margin: 0 0 0.35em; letter-spacing: -0.01em; }
h2 { font-size: 14.5pt; margin: 1.5em 0 0.45em; padding-bottom: 0.18em;
     border-bottom: 1px solid var(--rule); break-after: avoid; }
h3 { font-size: 11.8pt; margin: 1.25em 0 0.35em; break-after: avoid; }
h4 { font-size: 10.8pt; margin: 1em 0 0.3em; break-after: avoid; }
p { margin: 0 0 0.62em; orphans: 3; widows: 3; }
ul, ol { margin: 0.2em 0 0.75em; padding-left: 1.35em; }
li { margin: 0.18em 0; }
a { color: var(--accent); text-decoration: none; }
span.xref { color: var(--accent); }
code { font-family: 'DejaVu Sans Mono', Menlo, monospace; font-size: 0.86em;
       background: var(--fill); padding: 0.05em 0.25em; border-radius: 3px; }
pre { background: var(--fill); border: 1px solid var(--rule); border-radius: 6px;
      padding: 0.6em 0.8em; overflow: hidden; font-size: 0.86em; line-height: 1.4;
      break-inside: avoid; white-space: pre-wrap; }
pre code { background: none; padding: 0; font-size: 1em; }
table { border-collapse: collapse; width: 100%; margin: 0.4em 0 0.9em; font-size: 0.9em; }
tr { break-inside: avoid; }
thead { display: table-header-group; }
th { text-align: left; font-size: 0.92em; font-weight: 600; background: var(--fill); }
th, td { border-bottom: 1px solid var(--rule); padding: 0.32em 0.5em; vertical-align: top; }
blockquote { margin: 0.8em 0; padding: 0.55em 0.9em; border-left: 3px solid var(--rule);
             background: var(--fill); border-radius: 0 6px 6px 0; break-inside: avoid; }
blockquote p:last-child { margin-bottom: 0; }
blockquote.move { border-left-color: var(--accent); background: var(--accentFill); }
blockquote.finance { border-left-color: var(--ok); background: var(--okFill); }
blockquote.interview { border-left-color: var(--warn); background: var(--warnFill); }
blockquote.answer { background: #fff; border-left-color: var(--accent); }
blockquote.prompt { background: #fff; border-left: 3px solid var(--ink); font-size: 1.08em; font-style: italic; }
blockquote.track { background: #fff; border: 1px solid var(--rule); border-left: 3px solid var(--accent);
                   border-radius: 6px; padding: 0.5em 0.9em; }
blockquote.track p { margin: 0.12em 0; font-size: 0.86em; color: #374151; }
figure { margin: 0.9em 0 1.1em; break-inside: avoid; text-align: center; }
/* keep a lead-in sentence with the list, code, table, or answer it introduces */
p:has(+ ul), p:has(+ ol), p:has(+ pre), p:has(+ blockquote.answer) { break-after: avoid; }
figure svg { max-width: 100%; height: auto; max-height: 6.2in; }
figcaption { font-size: 0.82em; color: var(--muted); margin-top: 0.35em; text-align: left; }
.chapter { break-before: page; }
.eyebrow { text-transform: uppercase; letter-spacing: 0.12em; font-size: 8.5pt;
           color: var(--warn); font-weight: 700; margin-bottom: 0.4em; }
.cover { height: 9in; display: flex; flex-direction: column; justify-content: center; }
.cover h1 { font-size: 34pt; }
.cover p { font-size: 12pt; color: var(--muted); max-width: 5.2in; }
strong { font-weight: 700; }
"""

HEADER = (
    '<div style="font-family:Inter,Arial,sans-serif;font-size:7.5pt;color:#9aa4b2;width:100%;'
    'padding:0 0.9in;display:flex;justify-content:space-between;">'
    f'<span>{GUIDE_TITLE}</span><span>{TRACK_TITLE} · review preview</span></div>'
)
FOOTER = (
    '<div style="font-family:Inter,Arial,sans-serif;font-size:7.5pt;color:#9aa4b2;width:100%;'
    'padding:0 0.9in;text-align:center;"><span class="pageNumber"></span></div>'
)

CALLOUT_CLASSES = (
    ("Design move", "move"),
    ("Finance lens", "finance"),
    ("In the interview", "interview"),
    ("Level:", "track"),
)


def system_design_records(root: Path) -> List[Dict]:
    records = []
    for metadata_path in sorted((root / "content" / "system-design").glob("*/metadata.yaml")):
        metadata = load_data(metadata_path)
        metadata["_dir"] = metadata_path.parent
        records.append(metadata)
    return sorted(records, key=lambda m: (m.get("track_order", 10_000), m["id"]))


def _inline_svg(path: Path) -> str:
    svg = path.read_text(encoding="utf-8")
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
    svg = re.sub(r"<!DOCTYPE[^>]*>", "", svg, flags=re.DOTALL)
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.DOTALL)
    # Keep the natural width (never upscale) but let CSS shrink wide figures.
    width = re.search(r'<svg[^>]*?\swidth="([0-9.]+)(pt|px)?"', svg)
    svg = re.sub(r'(<svg[^>]*?)\swidth="[^"]*"', r"\1", svg, count=1)
    svg = re.sub(r'(<svg[^>]*?)\sheight="[^"]*"', r"\1", svg, count=1)
    if width:
        unit = width.group(2) or "px"
        svg = svg.replace("<svg", f'<svg style="width:{width.group(1)}{unit}"', 1)
    return svg.strip()


def markdown_to_html(markdown: str) -> str:
    result = subprocess.run(
        ["pandoc", "-f", "gfm", "-t", "html5", "--wrap=none"],
        input=markdown, capture_output=True, text=True, check=True,
    )
    return result.stdout


def _classify_blockquotes(body: str, in_followups_marker: str = "") -> str:
    def classify(match: "re.Match[str]") -> str:
        inner = match.group(1)
        text = re.sub(r"<[^>]+>", "", inner).strip()
        for prefix, cls in CALLOUT_CLASSES:
            if text.startswith(prefix):
                return f'<blockquote class="callout {cls}">{inner}</blockquote>'
        return match.group(0)

    return re.sub(r"<blockquote>(.*?)</blockquote>", classify, body, flags=re.DOTALL)


def render_chapter(root: Path, metadata: Dict, ids_in_build: Sequence[str]) -> str:
    package = metadata["_dir"]
    markdown = (package / metadata.get("content_file", "question.md")).read_text(encoding="utf-8")
    captions = {d["rendered_file"]: d for d in metadata.get("diagrams", [])}
    body = markdown_to_html(markdown)

    # Figures: inline the SVG and use the metadata caption.
    def figure(match: "re.Match[str]") -> str:
        src = html.unescape(match.group(1))
        name = Path(src).name
        svg_path = (package / src).resolve()
        info = captions.get(name, {})
        caption = html.escape(info.get("caption", ""))
        alt = html.escape(info.get("alt_text", ""))
        if not svg_path.is_file():
            return f'<p><em>Missing figure {html.escape(name)}</em></p>'
        return (
            f'<figure role="img" aria-label="{alt}">{_inline_svg(svg_path)}'
            f'<figcaption>{caption}</figcaption></figure>'
        )

    body = re.sub(r'<p>\s*<img src="([^"]+\.svg)"[^>]*/?>\s*</p>', figure, body)
    body = re.sub(r'<img src="([^"]+\.svg)"[^>]*/?>', figure, body)

    # Cross-question links become in-document anchors; handbook links become styled references.
    def link(match: "re.Match[str]") -> str:
        href, text = match.group(1), match.group(2)
        target = re.search(r"\.\./(sd-[a-z0-9-]+)/question\.md", href)
        if target and target.group(1) in ids_in_build:
            return f'<a href="#{target.group(1)}">{text}</a>'
        if "handbook-markdown" in href or href.endswith(".md"):
            return f'<span class="xref">{text}</span>'
        return match.group(0)

    body = re.sub(r'<a href="([^"]+)">(.*?)</a>', link, body)
    body = _classify_blockquotes(body)
    # The first plain blockquote after the H1-level track header is the prompt.
    body = re.sub(
        r'(<h2[^>]*>The question</h2>\s*)<blockquote>',
        r'\1<blockquote class="prompt">',
        body,
        count=1,
    )
    # Follow-up answers.
    def followups(match: "re.Match[str]") -> str:
        return match.group(0).replace("<blockquote>", '<blockquote class="answer">')

    body = re.sub(r'<h2[^>]*>Follow-ups</h2>.*?(?=<h2|\Z)', followups, body, flags=re.DOTALL)
    difficulty = int(metadata.get("difficulty", 3))
    level = "Foundation" if difficulty <= 2 else "Intermediate" if difficulty == 3 else "Advanced"
    eyebrow = f"System design · {level}"
    minutes = metadata.get("expected_duration_minutes")
    if minutes:
        eyebrow += f" · {minutes} minutes"
    return (
        f'<section class="chapter" id="{metadata["id"]}">'
        f'<div class="eyebrow">{html.escape(eyebrow)}</div>{body}</section>'
    )


def render_track_intro(root: Path) -> str:
    track = root / "content" / "system-design" / "TRACK.md"
    if not track.is_file():
        return ""
    body = markdown_to_html(track.read_text(encoding="utf-8"))

    def figure(match: "re.Match[str]") -> str:
        svg_path = (track.parent / html.unescape(match.group(1))).resolve()
        if not svg_path.is_file():
            return ""
        return f"<figure>{_inline_svg(svg_path)}</figure>"

    body = re.sub(r'<p>\s*<img src="([^"]+\.svg)"[^>]*/?>\s*</p>', figure, body)
    body = re.sub(r'<a href="\.\./\.\./release1[^"]*">(.*?)</a>', r'<span class="xref">\1</span>', body)
    body = re.sub(r'<a href="(sd-[a-z0-9-]+)/question\.md">(.*?)</a>', r'<a href="#\1">\2</a>', body)
    body = _classify_blockquotes(body)
    return f'<section class="chapter" id="track">{body}</section>'


def build(root: Path, ids: Optional[Sequence[str]], html_only: bool) -> Path:
    records = system_design_records(root)
    if ids:
        records = [r for r in records if r["id"] in ids]
    ids_in_build = [r["id"] for r in records]
    cover = (
        '<section class="cover"><div class="eyebrow">' + GUIDE_TITLE + "</div>"
        f"<h1>{TRACK_TITLE}</h1>"
        "<p>Pilot chapters for review. Each question teaches design moves that later questions reuse, "
        "and links to the companion handbook where the mechanism is taught.</p></section>"
    )
    parts = [cover]
    if not ids:
        parts.append(render_track_intro(root))
    parts.extend(render_chapter(root, record, ids_in_build) for record in records)
    document = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{TRACK_TITLE}</title><style>{CSS}</style></head><body>"
        + "\n".join(parts)
        + "</body></html>"
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "system-design-track-preview" if not ids else "-".join(ids)
    html_path = OUT_DIR / f"{stem}.html"
    html_path.write_text(document, encoding="utf-8")
    if html_only:
        return html_path
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed; wrote HTML only", file=sys.stderr)
        return html_path
    pdf_path = OUT_DIR / f"{stem}.pdf"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.resolve().as_uri())
        page.pdf(
            path=str(pdf_path),
            format="Letter",
            display_header_footer=True,
            header_template=HEADER,
            footer_template=FOOTER,
            margin={"top": "0.85in", "bottom": "0.8in", "left": "0.9in", "right": "0.9in"},
            print_background=True,
        )
        browser.close()
    return pdf_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--id", dest="ids", action="append")
    parser.add_argument("--html-only", action="store_true")
    args = parser.parse_args(argv)
    path = build(args.root.resolve(), args.ids, args.html_only)
    print(f"wrote {path.relative_to(args.root.resolve())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
