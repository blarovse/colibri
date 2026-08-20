#!/usr/bin/env python3
"""
Build the standalone single-file Jarvis app.

Inlines engine.js (and the icon) into index.html and strips the bits that only
work when hosted (manifest link, service worker). The result, jarvis-app.html,
is one file you can download, email to yourself, open from a phone or laptop —
fully offline, nothing to install.
"""

import base64
import pathlib
import re

HERE = pathlib.Path(__file__).parent
OUT = HERE / "jarvis-app.html"


def build() -> pathlib.Path:
    html = (HERE / "index.html").read_text(encoding="utf-8")
    engine = (HERE / "engine.js").read_text(encoding="utf-8")
    icon = base64.b64encode((HERE / "icon.svg").read_bytes()).decode()

    html = html.replace(
        '<link rel="manifest" href="manifest.webmanifest">',
        "",
    )
    html = html.replace(
        '<script src="engine.js"></script>',
        "<script>\n" + engine + "\n</script>",
    )
    # inline icon for the standalone file
    html = html.replace(
        "</head>",
        f'<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,{icon}">\n</head>',
    )
    # strip the service worker block (only valid when hosted over http(s))
    html = re.sub(
        r"/\* PWA service worker.*?\n(?=restore\(\); refresh\(\);)",
        "/* standalone file — no service worker needed */\n",
        html,
        flags=re.S,
    )
    # remove the hosted-only download button link target but keep the button working
    html = html.replace(
        'href="jarvis-app.html" download="jarvis-app.html"',
        'href="#" onclick="return false" title="You are already running the standalone app — save this page (Ctrl/Cmd-S) to keep it"',
    )

    OUT.write_text(html, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"built {path} ({path.stat().st_size / 1024:.1f} KiB)")
