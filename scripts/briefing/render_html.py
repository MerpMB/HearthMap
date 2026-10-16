# ruff: noqa: E501
"""Render docs/product/hearthmap-briefing-v0.1.md to a print-ready HTML page (and PDF when a Chromium browser exists).

The Markdown file stays canonical. This renderer understands only the subset the briefing uses (headings, paragraphs,
tables, lists, block quotes, images, horizontal rules, inline code/bold/italic/links and ```flow``` step diagrams), so no
Markdown dependency is added. The Markdown links the tracked snapshot (docs/product/hearthmap-briefing-v0.1/assets/);
the HTML references the same-named build plates relative to itself (outputs/briefing/maps/). HTML and PDF are rendered
derivatives and stay in the git-ignored outputs/briefing/.

Layout hints are HTML comments in the Markdown (GitHub does not display them):
  <!-- cover --> ... <!-- /cover -->          the cover page
  <!-- page -->                               start a new page before the next block
  <!-- landscape --> ... <!-- /landscape -->  put the enclosed sections on A4 landscape pages (wide plates)
  <!-- columns --> ... <!-- /columns -->      two columns, one per ### sub-heading
  <!-- grid side|half --> A <!-- | --> B <!-- /grid -->  side-by-side blocks (side: a figure beside its notes)
  <!-- fig short|tall -->                     size class for the next figure

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
RUNNING_HEAD = "HearthMap · Spatial Evidence Briefing v0.1"
RUNNING_STATE = "DRAFT · SCORING OFF · REVIEW PENDING"

# Document system: deep forest/teal accent, limestone/ivory callouts, restrained terrain brown. Map palettes are untouched.
CSS = """
:root{--paper:#FBF9F4;--ink:#262826;--muted:#6B6A63;--rule:#DCD6CA;--accent:#1F4E4A;--accent-soft:#E3ECE9;
--ivory:#F4EFE4;--terrain:#8A5A3B;--card:#FFFFFF}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"IBM Plex Sans Thai","Leelawadee UI","Sarabun",Tahoma,sans-serif;font-size:15px;line-height:1.6}
main{max-width:1040px;margin:0 auto;padding:40px 24px 80px}
h1{font-size:64px;line-height:1;margin:0;letter-spacing:-1.5px;color:var(--accent)}
h2{font-size:23px;line-height:1.3;margin:30px 0 10px;padding-top:12px;border-top:2.5px solid var(--accent);color:var(--ink);break-after:avoid}
h2 .num{display:inline-block;min-width:44px;margin-right:10px;color:var(--terrain);font-weight:700;letter-spacing:.5px}
h3{font-size:16.5px;margin:18px 0 6px;color:var(--accent);break-after:avoid}
p{margin:7px 0}
code{font-family:Consolas,"Cascadia Mono",monospace;font-size:.84em;background:#EEEAE0;padding:1px 5px;border-radius:3px}
a{color:var(--accent)}
figure{margin:10px 0;break-inside:avoid}
figure img{display:block;max-width:100%;height:auto;margin:0 auto;border:1px solid var(--rule);background:#fff}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:13.2px;background:var(--card)}
tr{break-inside:avoid}
th,td{border:1px solid var(--rule);padding:4px 7px;vertical-align:top;text-align:left}
th{background:var(--accent-soft);font-weight:600}
blockquote{margin:10px 0;padding:8px 14px;border-left:4px solid var(--terrain);background:var(--ivory);break-inside:avoid}
blockquote p{margin:3px 0}
hr{border:0;border-top:1px solid var(--rule);margin:26px 0}
ul,ol{padding-left:22px;margin:6px 0}
li{margin:2px 0}
.pb{height:0}
.flow{display:flex;flex-direction:column;gap:0;margin:12px 0;max-width:720px;break-inside:avoid}
.flow .step{background:var(--card);border:1px solid var(--rule);border-left:5px solid var(--accent);padding:7px 14px;border-radius:4px}
.flow .step.now{border-left-color:var(--terrain);background:var(--ivory);font-weight:600}
.flow .step small{display:block;color:var(--muted);font-weight:400}
.flow .arrow{text-align:center;color:var(--muted);font-size:16px;line-height:1.3}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:12px 0}
.cols .col{background:var(--card);border:1px solid var(--rule);border-radius:6px;padding:4px 18px 12px}
.cols .col:first-child{border-top:6px solid var(--accent)}
.cols .col:last-child{border-top:6px solid var(--terrain);background:var(--ivory)}
.cols .col h3{margin-top:12px}
.cols .col li{margin:6px 0}
.grid{display:grid;gap:16px;align-items:start;margin:8px 0}
.grid.side{grid-template-columns:1.3fr 1fr}
.grid.sidetall{grid-template-columns:auto 1fr}
.grid.half{grid-template-columns:1.5fr 1fr}
.grid.pair{grid-template-columns:1fr 1fr}
.grid.pair h3{margin-top:0}
.grid .cell>:first-child{margin-top:0}
.grid.side figure,.grid.sidetall figure{margin:0}
.grid.sidetall figure img{max-width:none;width:auto;max-height:640px}
.cover{display:flex;flex-direction:column;min-height:92vh;padding-top:10px}
.cover .kicker{font-size:28px;font-weight:600;margin:6px 0 18px;color:var(--ink)}
.cover .thai{font-size:19px;line-height:1.55;max-width:720px;color:var(--ink);margin:0}
.cover .place{font-size:15px;color:var(--muted);letter-spacing:.3px;margin:14px 0 0}
.cover .status{align-self:flex-start;display:inline-block;margin:18px 0 0;padding:4px 12px;border:1.5px solid var(--terrain);color:var(--terrain);border-radius:3px;font-size:13px;letter-spacing:1px;font-weight:600;background:transparent;font-family:inherit}
.cover figure{margin:auto 0 0;align-self:flex-end;width:78%}
.cover figure img{border:0;background:transparent}
footer{margin-top:40px;font-size:12px;color:var(--muted);border-top:1px solid var(--rule);padding-top:10px}
@media (max-width:640px){main{padding:24px 16px}h1{font-size:44px}.cols{grid-template-columns:1fr}table{font-size:12.5px;display:block;overflow-x:auto}.cover figure{width:100%}}
@page{size:A4;margin:17mm 13mm 15mm;
 @top-left{content:"HEAD";font:8pt "Leelawadee UI",Tahoma,sans-serif;color:#6B6A63}
 @top-right{content:"STATE";font:8pt "Leelawadee UI",Tahoma,sans-serif;color:#8A5A3B}
 @bottom-right{content:counter(page) " / " counter(pages);font:8pt "Leelawadee UI",Tahoma,sans-serif;color:#6B6A63}}
@page wide{size:A4 landscape;margin:14mm 13mm 11mm}
@page cover{margin:16mm 16mm;@top-left{content:none}@top-right{content:none}@bottom-right{content:none}}
@media print{
 body{background:#fff;font-size:10.6pt}
 main{max-width:none;padding:0}
 hr{display:none}
 .pb{break-before:page}
 h2{margin-top:6mm}
 h2:first-child,.pb+h2{margin-top:0}
 .cover{page:cover;min-height:262mm;break-after:page}
 .cover figure{width:72%}
 .landscape{page:wide}
 figure img{max-height:198mm;width:auto}
 .landscape figure img{max-height:150mm}
 .landscape .grid.side figure img{max-height:150mm}
 .landscape .grid.sidetall figure img{max-height:132mm}
 .landscape .grid.pair figure img{max-height:80mm}
 .landscape figure.short img{max-height:72mm}
 .landscape figure.tall img{max-height:148mm}
 .landscape table{width:99.6%}
 .landscape p,.landscape li{font-size:9.8pt}
 .landscape li{margin:1px 0}
 .landscape .grid{line-height:1.45}
 .landscape .grid p{margin:4px 0}
 .landscape .grid td,.landscape .grid th{padding:3px 6px}
 .flow{flex-direction:row;max-width:none}
 .flow .step{flex:1;padding:6px 8px;font-size:9.4pt}
 .flow .step small{font-size:8.2pt}
 .flow .arrow{display:flex;align-items:center;padding:0 3px;font-size:0}
 .flow .arrow::after{content:"→";font-size:13pt;color:#6B6A63}
 .cover figure img{max-height:150mm}
 table{font-size:9.6pt}
 .cols{break-inside:avoid}
}
""".replace("HEAD", RUNNING_HEAD).replace("STATE", RUNNING_STATE)


def inline(text: str) -> str:
    codes: list[str] = []

    def stash(m: re.Match) -> str:
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"

    s = re.sub(r"`([^`]+)`", stash, text)  # code spans are protected so bold/italic may wrap them
    s = html.escape(s, quote=False)
    s = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", lambda m: img(m.group(2), m.group(1)), s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(\S(?:.*?\S)?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", s)
    s = s.replace("\\*", "*")
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], s)


FIG_CLASS: list[str] = []  # set by <!-- fig X --> for the next figure


def img(src: str, alt: str) -> str:
    if src.startswith(IMG_PREFIX):
        src = "maps/" + src[len(IMG_PREFIX) :]
    cls = f' class="{FIG_CLASS.pop()}"' if FIG_CLASS else ""
    return f'<figure{cls}><img src="{src}" alt="{alt}"></figure>'


def table(rows: list[str]) -> str:
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    head, body = cells[0], list(cells[2:])
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


def heading(level: int, text: str) -> str:
    if level == 2 and (m := re.match(r"^(\d+)\.\s+(.*)", text)):
        return f'<h2><span class="num">{int(m.group(1)):02d}</span>{inline(m.group(2))}</h2>'
    return f"<h{level}>{inline(text)}</h{level}>"


def columns(lines: list[str]) -> str:
    groups: list[list[str]] = []
    for line in lines:
        if line.startswith("### ") or not groups:
            groups.append([])
        groups[-1].append(line)
    return (
        '<div class="cols">'
        + "".join(f'<div class="col">{convert(chr(10).join(g))}</div>' for g in groups)
        + "</div>"
    )


def cover(lines: list[str]) -> str:
    """Cover block: title, kicker, Thai subtitle, place line, status chip, AOI visual."""
    out, paras = [], [x for x in lines if x.strip()]
    for line in paras:
        if line.startswith("# "):
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("!["):
            out.append(inline(line))
        elif line.startswith("**"):
            out.append(f'<p class="kicker">{inline(line.strip("*"))}</p>')
        elif line.startswith("`"):
            out.append(f'<p class="status">{html.escape(line.strip("`"))}</p>')
        elif "·" in line:
            out.append(f'<p class="place">{inline(line)}</p>')
        else:
            out.append(f'<p class="thai">{inline(line)}</p>')
    return '<section class="cover">' + "".join(out) + "</section>"


def block_until(lines: list[str], i: int, end: str) -> tuple[list[str], int]:
    block = []
    while i < len(lines) and lines[i].strip() != end:
        block.append(lines[i])
        i += 1
    return block, i + 1


def convert(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        tag = line.strip()
        if tag == "<!-- page -->":
            out.append('<div class="pb"></div>')
            i += 1
            continue
        if tag == "<!-- landscape -->":
            out.append('<div class="landscape">')
            i += 1
            continue
        if tag == "<!-- /landscape -->":
            out.append("</div>")
            i += 1
            continue
        if tag == "<!-- cover -->":
            block, i = block_until(lines, i + 1, "<!-- /cover -->")
            out.append(cover(block))
            continue
        if m := re.match(r"^<!-- fig (\w+) -->$", tag):
            FIG_CLASS[:] = [m.group(1)]
            i += 1
            continue
        if m := re.match(r"^<!-- grid (\w+) -->$", tag):
            block, i = block_until(lines, i + 1, "<!-- /grid -->")
            parts: list[list[str]] = [[]]
            for b in block:
                if b.strip() == "<!-- | -->":
                    parts.append([])
                else:
                    parts[-1].append(b)
            cells = "".join(f'<div class="cell">{convert(chr(10).join(x))}</div>' for x in parts)
            out.append(f'<div class="grid {m.group(1)}">{cells}</div>')
            continue
        if tag == "<!-- columns -->":
            block, i = block_until(lines, i + 1, "<!-- /columns -->")
            out.append(columns(block))
            continue
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
        if not line.strip() or (tag.startswith("<!--") and tag.endswith("-->")):
            i += 1
            continue
        if m := re.match(r"^(#{1,4}) (.*)", line):
            out.append(heading(len(m.group(1)), m.group(2)))
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
            tag_ = "ol" if ordered else "ul"
            out.append(f"<{tag_}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag_}>")
            continue
        para = [line]
        i += 1
        while (
            i < len(lines)
            and lines[i].strip()
            and not re.match(r"^(#|\||>|- |\d+\. |```|---|<!--)", lines[i])
        ):
            para.append(lines[i])
            i += 1
        text = " ".join(p.strip() for p in para)
        out.append(inline(text) if text.startswith("![") else f"<p>{inline(text)}</p>")
    return "\n".join(out)


def build_html() -> str:
    body = convert(SRC.read_text("utf-8"))
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
{body}
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
