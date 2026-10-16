# ruff: noqa: E501
"""Render docs/product/hearthmap-briefing-v0.1.md to a print-ready HTML page (and PDF when a Chromium browser exists).

The Markdown file stays canonical. This renderer understands only the subset the briefing uses (headings, paragraphs,
tables, lists, block quotes, images, horizontal rules, inline code/bold/italic/links and ```flow``` step diagrams), so no
Markdown dependency is added. The Markdown links the tracked snapshot (docs/product/hearthmap-briefing-v0.1/assets/);
the HTML references the same-named build plates relative to itself (outputs/briefing/maps/). HTML and PDF are rendered
derivatives and stay in the git-ignored outputs/briefing/.

Usage:  python scripts/briefing/render_html.py [--no-pdf]
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs/product/hearthmap-briefing-v0.1.md"
OUT = ROOT / "outputs/briefing"
HTML_OUT = OUT / "hearthmap-briefing-v0.1.html"
PDF_OUT = OUT / "hearthmap-briefing-v0.1.pdf"
# The Markdown links the tracked snapshot; the rendered HTML uses the matching build plates in outputs/briefing/maps/.
IMG_PREFIX = "hearthmap-briefing-v0.1/assets/"

CSS = """
:root{--paper:#FAF8F3;--ink:#2B2B2B;--muted:#6E6A62;--rule:#DDD8CD;--accent:#3E5C76;--warm:#9B6A5C;--card:#FFFFFF}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"IBM Plex Sans Thai","Leelawadee UI","Sarabun",Tahoma,sans-serif;font-size:15px;line-height:1.65}
main{max-width:1040px;margin:0 auto;padding:40px 24px 80px}
h1{font-size:40px;line-height:1.15;margin:0 0 6px;letter-spacing:-.5px}
h1+p strong{font-size:19px;font-weight:600;color:var(--muted)}
h2{font-size:25px;margin:56px 0 12px;padding-top:18px;border-top:2px solid var(--ink);break-before:page}
h3{font-size:18px;margin:28px 0 8px;color:var(--accent)}
p{margin:10px 0}
code{font-family:Consolas,"Cascadia Mono",monospace;font-size:.86em;background:#EFECE4;padding:1px 5px;border-radius:3px}
a{color:var(--accent)}
img{display:block;max-width:100%;height:auto;margin:16px auto;border:1px solid var(--rule);background:#fff}
figure{margin:18px 0}
figcaption{font-size:12.5px;color:var(--muted);text-align:center}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:13.5px;background:var(--card)}
th,td{border:1px solid var(--rule);padding:6px 9px;vertical-align:top;text-align:left}
th{background:#EFECE4;font-weight:600}
blockquote{margin:16px 0;padding:10px 16px;border-left:4px solid var(--warm);background:#F3EFE7}
blockquote p{margin:4px 0}
hr{border:0;border-top:1px solid var(--rule);margin:32px 0}
ul,ol{padding-left:24px}
li{margin:3px 0}
.flow{display:flex;flex-direction:column;align-items:stretch;gap:0;margin:18px 0;max-width:720px}
.flow .step{background:var(--card);border:1px solid var(--rule);border-left:5px solid var(--accent);padding:9px 14px;border-radius:4px}
.flow .step.now{border-left-color:var(--warm);background:#F6EFE9;font-weight:600}
.flow .step small{display:block;color:var(--muted);font-weight:400}
.flow .arrow{text-align:center;color:var(--muted);font-size:18px;line-height:1.4}
.cover{min-height:92vh}
.stamp{display:inline-block;border:1.5px solid var(--warm);color:var(--warm);padding:2px 10px;border-radius:3px;font-size:12.5px;letter-spacing:.5px;margin:6px 0 18px}
footer{margin-top:60px;font-size:12px;color:var(--muted);border-top:1px solid var(--rule);padding-top:12px}
@media (max-width:640px){main{padding:24px 16px}h1{font-size:30px}table{font-size:12.5px;display:block;overflow-x:auto}}
@media print{body{background:#fff;font-size:11.5pt}main{max-width:none;padding:0}h2{margin-top:0}hr{display:none}.cover{min-height:0}.cover img{max-height:170mm}.cover blockquote{font-size:9.5pt}img{max-height:235mm;width:auto}table,blockquote,.flow,img{break-inside:avoid}}
@page{size:A4;margin:14mm 13mm}
"""


def inline(text: str) -> str:
    out, parts = [], re.split(r"(`[^`]+`)", text)
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(f"<code>{html.escape(part[1:-1])}</code>")
            continue
        s = html.escape(part, quote=False)
        s = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", lambda m: img(m.group(2), m.group(1)), s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", s)
        s = s.replace("\\*", "*")
        out.append(s)
    return "".join(out)


def img(src: str, alt: str) -> str:
    if src.startswith(IMG_PREFIX):
        src = "maps/" + src[len(IMG_PREFIX) :]
    return f'<figure><img src="{src}" alt="{alt}" loading="lazy"><figcaption>{alt}</figcaption></figure>'


def table(rows: list[str]) -> str:
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    head, body = cells[0], [r for r in cells[2:]]
    h = "".join(f"<th>{inline(c)}</th>" for c in head)
    b = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
    thead = f"<thead><tr>{h}</tr></thead>" if any(head) else ""
    return f"<table>{thead}<tbody>{b}</tbody></table>"


def flow(lines: list[str]) -> str:
    parts = []
    for i, line in enumerate(lines):
        label, _, note = line.partition("◀")
        title, _, detail = label.partition(" — ")
        now = "อยู่ตรงนี้" in note or "แข็งแรงที่สุด" in note
        body = f"{html.escape(title.strip())}<small>{html.escape(detail.strip())}{' · ' + html.escape(note.strip()) if note.strip() else ''}</small>"
        parts.append(f'<div class="step{" now" if now else ""}">{body}</div>')
        if i < len(lines) - 1:
            parts.append('<div class="arrow">↓</div>')
    return f'<div class="flow">{"".join(parts)}</div>'


def convert(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            lang = line[3:].strip()
            block = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            out.append(
                flow(block)
                if lang == "flow"
                else f"<pre><code>{html.escape(chr(10).join(block))}</code></pre>"
            )
            continue
        if not line.strip():
            i += 1
            continue
        if m := re.match(r"^(#{1,4}) (.*)", line):
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
            i += 1
            continue
        if line.strip() == "---":
            out.append("<hr>")
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(table(rows))
            continue
        if line.startswith(">"):
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(lines[i][1:].strip())
                i += 1
            paras = "\n".join(block).split("\n\n")
            out.append(
                "<blockquote>"
                + "".join(
                    f"<p>{'<br>'.join(inline(x) for x in p.splitlines() if x)}</p>" for p in paras
                )
                + "</blockquote>"
            )
            continue
        if re.match(r"^(- |\d+\. )", line):
            ordered = bool(re.match(r"^\d+\. ", line))
            items = []
            while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
                items.append(re.sub(r"^(- |\d+\. )", "", lines[i]))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        para = [line]
        i += 1
        while (
            i < len(lines)
            and lines[i].strip()
            and not re.match(r"^(#|\||>|- |\d+\. |```|---)", lines[i])
        ):
            para.append(lines[i])
            i += 1
        text = " ".join(p.strip() for p in para)
        out.append(inline(text) if text.startswith("![") else f"<p>{inline(text)}</p>")
    return "\n".join(out)


def build_html() -> str:
    md = SRC.read_text("utf-8")
    body = convert(md)
    # the cover: everything before the first <h2> gets its own page with a review stamp
    cut = body.find("<h2>")
    cover, rest = body[:cut], body[cut:]
    cover = cover.replace(
        "</h1>",
        '</h1>\n<div class="stamp">DRAFT · HEARTHMAP_BRIEFING_V0_1_REVIEW = PENDING</div>',
        1,
    )
    return f"""<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HearthMap Spatial Evidence Briefing v0.1</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Thai:wght@400;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<main>
<section class="cover">
{cover}
</section>
{rest}
<footer>Generated from <code>docs/product/hearthmap-briefing-v0.1.md</code> by <code>scripts/briefing/render_html.py</code>.
Descriptive only · no score · no ranking · no recommendation · <code>FAMILY_SCORING_ALLOWED = false</code></footer>
</main>
</body>
</html>
"""


def find_browser() -> str | None:
    for cand in (
        shutil.which("msedge"),
        shutil.which("chrome"),
        shutil.which("chromium"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ):
        if cand and Path(cand).exists():
            return cand
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args(argv)
    missing = [
        m
        for m in re.findall(r"\(hearthmap-briefing-v0\.1/assets/([^)]+)\)", SRC.read_text("utf-8"))
        if not (OUT / "maps" / m).exists()
    ]
    if missing:
        print("missing plates (run scripts/briefing/make_plates.py first):", missing)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    HTML_OUT.write_text(build_html(), encoding="utf-8")
    print("wrote", HTML_OUT)
    if args.no_pdf:
        return 0
    browser = find_browser()
    if browser is None:
        print("no Chromium-based browser found; HTML only")
        return 0
    subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={PDF_OUT}",
            HTML_OUT.as_uri(),
        ],
        check=True,
        capture_output=True,
        timeout=180,
    )
    print("wrote", PDF_OUT, f"({PDF_OUT.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
