"""Assemble the static GitHub Pages demo from the real dashboard and engine.

The dashboard (static/) is reused as-is; only its asset paths change and a
script is added that answers /api calls from Python running in the browser.
The FastAPI, CLI and Prometheus modules are left out: the page does not need
them and they are not available in Pyodide.

Usage: python web/build_site.py [output_dir]   (default: _site)
Preview: python -m http.server -d _site 8000
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PACKAGE = ROOT / "src" / "reliability_control_plane"
SERVER_ONLY = {"app.py", "cli.py", "__main__.py", "metrics.py", "__init__.py"}
PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js"
REPO = "https://github.com/amandesi13/reliability-control-plane"

PAGE_EDITS = [
    ('href="/static/styles.css"', 'href="styles.css"'),
    (
        '<script src="/static/app.js" defer></script>',
        f'<script src="{PYODIDE}"></script>\n'
        '    <script src="pyodide-api.js"></script>\n'
        '    <script src="app.js" defer></script>',
    ),
    ('href="/" aria-label', 'href="./" aria-label'),
    (
        'href="/docs" title="OpenAPI documentation"',
        f'href="{REPO}#api-example" title="API reference (the hosted app serves OpenAPI at /docs)"',
    ),
    ("<span>Demo environment</span>", "<span>Runs in your browser</span>"),
]


def build(out: Path) -> Path:
    if out.exists():
        shutil.rmtree(out)
    (out / "py" / PACKAGE.name / "policies").mkdir(parents=True)

    page = (PACKAGE / "static" / "index.html").read_text(encoding="utf-8")
    for old, new in PAGE_EDITS:
        if old not in page:
            raise SystemExit(f"dashboard markup changed, cannot find: {old}")
        page = page.replace(old, new)
    (out / "index.html").write_text(page, encoding="utf-8")
    shutil.copy(PACKAGE / "static" / "app.js", out / "app.js")
    shutil.copy(PACKAGE / "static" / "styles.css", out / "styles.css")
    shutil.copy(WEB / "pyodide-api.js", out / "pyodide-api.js")

    files = ["bridge.py", f"{PACKAGE.name}/__init__.py"]
    shutil.copy(WEB / "bridge.py", out / "py" / "bridge.py")
    # The real __init__ imports the FastAPI app; the browser build only needs the engine.
    (out / "py" / PACKAGE.name / "__init__.py").write_text(
        '"""Reliability Control Plane (browser build: engine only)."""\n\n__version__ = "1.0.0"\n',
        encoding="utf-8",
    )
    for source in sorted(PACKAGE.glob("*.py")):
        if source.name in SERVER_ONLY:
            continue
        shutil.copy(source, out / "py" / PACKAGE.name / source.name)
        files.append(f"{PACKAGE.name}/{source.name}")
    for policy in sorted((PACKAGE / "policies").glob("*.json")):
        shutil.copy(policy, out / "py" / PACKAGE.name / "policies" / policy.name)
        files.append(f"{PACKAGE.name}/policies/{policy.name}")

    (out / "py" / "manifest.json").write_text(json.dumps(files, indent=1), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return out


if __name__ == "__main__":
    target = build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site")
    print(f"site written to {target}")
