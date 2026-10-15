"""Build Grid_Stress_Analysis_Report.pdf from Grid_Stress_Analysis_Report.md.

Converts the markdown to styled HTML (images inlined as base64 data URIs),
then prints to PDF with headless Edge.
"""
import base64
import mimetypes
import re
import subprocess
from pathlib import Path

import markdown

ROOT = Path(r"C:\Users\mltsw\OneDrive\Desktop\Projects\grid-fragility-analysis")
MD = ROOT / "Grid_Stress_Analysis_Report.md"
BUILD = ROOT / "_report_build"
HTML_OUT = BUILD / "report.html"
PDF_OUT = ROOT / "Grid_Stress_Analysis_Report.pdf"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

text = MD.read_text(encoding="utf-8")

# Split off the cover preamble: everything before "## 1. Executive Summary"
marker = "## 1. Executive Summary"
idx = text.index(marker)
body_md = text[idx:]

COVER = """
<div class="cover">
  <div class="cover-inner">
    <h1 class="cover-title">Grid Stress Analysis</h1>
    <p class="cover-subtitle">An Applied Analysis of Grid Operating Regimes Using Public Operational Data</p>
    <p class="cover-byline">By Miles Wolf</p>
    <p class="cover-date">June 2026</p>
    <p class="cover-note">Supersedes <em>Electric Grid Fragility Analysis</em> (original January 2026, revised April 2026)</p>
  </div>
  <p class="cover-link">Full documentation and codebase available here &mdash;<br>
  <a href="https://github.com/miles-wolf/Grid-Stress-Analysis">https://github.com/miles-wolf/Grid-Stress-Analysis</a></p>
</div>
"""

html_body = markdown.markdown(body_md, extensions=["tables", "fenced_code"])

# Inline images as data URIs (paths in md are relative to project root)
def inline_img(m):
    src = m.group(1)
    p = ROOT / src.replace("/", "\\")
    if not p.exists():
        raise FileNotFoundError(p)
    mime = mimetypes.guess_type(str(p))[0] or "image/png"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f'src="data:{mime};base64,{b64}"'

html_body = re.sub(r'src="([^"]+)"', inline_img, html_body)

# Wrap caption-paragraph + image-paragraph pairs in a no-break figure div.
# Caption must be a single paragraph (no </p> inside) immediately followed by
# an image-only paragraph.
html_body = re.sub(
    r'(<p><strong>Figure[^<]*</strong>(?:(?!</p>).)*</p>)\s*(<p><img[^>]*></p>)',
    r'<div class="fig">\1\2</div>',
    html_body,
    flags=re.DOTALL,
)
# Any remaining bare image paragraphs also avoid breaking
html_body = re.sub(r'<p>(<img[^>]*>)</p>', r'<p class="imgp">\1</p>', html_body)

CSS = """
@page { size: Letter; margin: 0.85in 0.8in; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; }
body {
  font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
  font-size: 10pt; line-height: 1.5; color: #1a1a1a; margin: 0;
}
.cover { page-break-after: always; text-align: center; position: relative; height: 9.1in; }
.cover-inner { padding-top: 3.1in; }
.cover-title { font-size: 30pt; font-weight: 650; margin: 0 0 14pt 0; letter-spacing: 0.3pt; }
.cover-subtitle { font-size: 13pt; color: #444; margin: 0 0 42pt 0; }
.cover-byline { font-size: 12pt; font-weight: 600; margin: 0 0 6pt 0; }
.cover-date { font-size: 11pt; margin: 0 0 4pt 0; }
.cover-note { font-size: 9.5pt; color: #666; margin: 0; }
.cover-link { position: absolute; bottom: 0; width: 100%; font-size: 9.5pt; color: #555; }
.cover-link a { color: #1a56a0; text-decoration: none; }

h2 {
  font-size: 14.5pt; font-weight: 650; color: #14365c;
  border-bottom: 1.5px solid #b8c6d8; padding-bottom: 3pt;
  margin: 22pt 0 8pt 0; page-break-after: avoid;
}
h2:first-of-type { margin-top: 0; }
h3 { font-size: 11.5pt; font-weight: 650; color: #1f4a7a; margin: 14pt 0 5pt 0; page-break-after: avoid; }
p { margin: 6pt 0; orphans: 3; widows: 3; }
ul, ol { margin: 6pt 0 6pt 0; padding-left: 22pt; }
li { margin: 3.5pt 0; }
strong { font-weight: 650; }
a { color: #1a56a0; }
hr { display: none; }

code, pre {
  font-family: Consolas, 'Courier New', monospace; font-size: 9pt;
  background: #f4f6f9;
}
pre {
  padding: 8pt 10pt; border: 1px solid #dde4ec; border-radius: 3px;
  line-height: 1.45; page-break-inside: avoid; white-space: pre-wrap;
}

table {
  border-collapse: collapse; margin: 8pt auto; font-size: 9pt;
  page-break-inside: avoid;
}
th, td { border: 1px solid #c4cfdb; padding: 3.5pt 8pt; text-align: left; }
th { background: #e8eef5; font-weight: 650; color: #14365c; }
tr:nth-child(even) td { background: #f7f9fb; }

.fig { page-break-inside: avoid; margin: 8pt 0; text-align: center; }
.fig p { margin: 4pt 0; }
.fig p:first-child { font-size: 9pt; color: #333; text-align: left; }
img { max-width: 100%; height: auto; }
.fig img { max-height: 3.8in; width: auto; max-width: 100%; }
.imgp { text-align: center; }
"""

# Add page break before Appendix A heading
html_body = html_body.replace(
    "<h2>Appendix A:",
    '<h2 style="page-break-before: always;">Appendix A:',
)

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Grid Stress Analysis</title>
<style>{CSS}</style></head>
<body>
{COVER}
{html_body}
</body></html>"""

HTML_OUT.write_text(html, encoding="utf-8")
print("wrote", HTML_OUT, len(html), "chars")

subprocess.run(
    [
        EDGE,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=20000",
        f"--print-to-pdf={PDF_OUT}",
        HTML_OUT.as_uri(),
    ],
    check=True,
    timeout=180,
)
print("wrote", PDF_OUT, PDF_OUT.stat().st_size, "bytes")
