"""Build the website into build/site: python tools/build_site.py

The site is a short showcase: a home page that routes each problem to its product, and one page per product. Pages in
website/ hold only their content; this wraps each with the shared head, header and footer. The screenshots are real product
output, made by tools/capture_screens.py from the consoles in this checkout; each records a digest of the files it was made
from, and the website tests fail when a screenshot no longer matches them. Earlier addresses redirect to the product page.
"""
import hashlib
import re
import shutil
import struct
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC, OUT = ROOT / "website", ROOT / "build" / "site"
SECTIONS = {"qreadiness": "Acxelin QReadiness", "qguard": "Acxelin QGuard", "qvpn": "Acxelin QVPN"}
MOVED = {"edge": "qguard", "vpn": "qvpn", "readiness": "qreadiness"}  # earlier addresses, kept as redirects
REMOVED = ["how-it-works.html", "set-up.html", "manual.html", "demo.html", "security.html", "assets.html", "sample.html", "sample-report.html"]
SHELL = "core/src/acxelin_core/assets/shell.css"
CONTACT = ("https://forms.office.com/Pages/ResponsePage.aspx?id=G7il0FYBPk-mQiu5eNm4__Zpyi-xUOBMtEt0p-905AxUME9LMzZF"
           "V0JLWEFDMzdJMTM1MzYxSEVORy4u")  # the company's own contact form, the same one acxelinquantum.com uses
EMAIL = "info@acxelinquantum.com"
FILMS = {s: f"assets/films/{s}" for s in ("qguard", "qvpn", "qreadiness")}  # .mp4 (720p), .jpg (poster), .vtt (captions)
SCREENS = {  # each screenshot and the files that decide what it shows
    "qguard-console.png": [SHELL, "products/tls/src/acxelin_tls/console.html"],
    "qvpn-console.png": [SHELL, "products/vpn/src/acxelin_vpn/console.html"],
    "qvpn-app.png": [SHELL, "products/vpn/src/acxelin_vpn/app.html"],
    "qreadiness-console.png": [SHELL, "products/readiness/src/acxelin_readiness/console.html"],
}
KEY = "acxelin-source"
LAYOUT = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="icon" href="{root}assets/acxelin-quantum.svg" type="image/svg+xml">
<link rel="stylesheet" href="{root}assets/site.css?v={css}">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="wrap bar">
<a href="{root}index.html" aria-label="Acxelin Quantum, all products">{logo}</a>
<nav aria-label="{nav_label}">{nav}</nav>
<a class="btn primary small talk" href="{contact}">Talk to an Expert</a>
</div></header>
<main id="main">
{body}
</main>
<footer><div class="wrap"><span>{footer}</span><nav aria-label="Company"><a href="{contact}">Talk to an Expert</a><a href="mailto:{email}">{email}</a><a href="https://acxelinquantum.com/">acxelinquantum.com</a><a href="{root}index.html">All products</a></nav></div></footer>
</body>
</html>
"""


def digest(screen):
    """What a screenshot was made from: a SHA-256 over its source files, line endings normalised (a Windows checkout matches)."""
    h = hashlib.sha256()
    for rel in SCREENS[screen]:
        h.update(rel.encode() + b"\0" + (ROOT / rel).read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def png_text(path):
    """The tEXt fields of a PNG, as {keyword: text}."""
    data, out, i = Path(path).read_bytes(), {}, 8
    while i + 8 <= len(data):
        n, kind = struct.unpack(">I4s", data[i:i + 8])
        if kind == b"tEXt":
            k, _, v = data[i + 8:i + 8 + n].partition(b"\0")
            out[k.decode("latin-1")] = v.decode("latin-1")
        i += 12 + n
    return out


def with_text(png, key, value):
    """The PNG with a tEXt field added after its header."""
    body = key.encode("latin-1") + b"\0" + value.encode("latin-1")
    chunk = struct.pack(">I", len(body)) + b"tEXt" + body + struct.pack(">I", zlib.crc32(b"tEXt" + body) & 0xFFFFFFFF)
    end = 8 + 12 + struct.unpack(">I", png[8:12])[0]
    return png[:end] + chunk + png[end:]


def logo():
    svg = (ROOT / "website/assets/acxelin-quantum.svg").read_text(encoding="utf-8")
    return svg.replace('class="logo"', 'class="logo" aria-hidden="true" focusable="false"')


def nav(section):
    if not section:
        return "".join(f'<a href="{key}/index.html">{name}</a>' for key, name in SECTIONS.items())
    return f'<a href="index.html" aria-current="page">{SECTIONS[section]}</a>'


def redirect(to):
    return (f'<!doctype html><meta charset="utf-8"><title>Moved</title><meta http-equiv="refresh" content="0; url={to}">'
            f'<link rel="canonical" href="{to}"><a href="{to}">This page moved.</a>\n')


def main():
    for _ in range(6):  # a sync tool or virus scanner can hold freshly written files for a while
        shutil.rmtree(OUT, ignore_errors=True)
        if not OUT.exists():
            break
        time.sleep(0.5)
    if OUT.exists():  # still held: build over it, replacing every file this build writes
        print(f"note: could not clear {OUT} (a file in it is held open); building over it")
    shutil.copytree(SRC / "assets", OUT / "assets", dirs_exist_ok=True)
    mark = logo()
    css = hashlib.sha256((SRC / "assets/site.css").read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:10]  # a new stylesheet gets a new address
    for src in sorted(SRC.rglob("*.html")):
        rel = src.relative_to(SRC)
        text = src.read_text(encoding="utf-8")
        meta = re.match(r"<!-- title: (.*?) -->\n<!-- description: (.*?) -->\n", text)
        if not meta:
            sys.exit(f"{rel}: the first two lines must be the title and description comments")
        section = rel.parts[0] if len(rel.parts) > 1 else None
        root = "../" if section else ""
        name = SECTIONS[section] if section else "Acxelin Quantum"
        footer = "© 2026 Acxelin Quantum, all rights reserved."
        values = {"title": meta.group(1), "description": meta.group(2), "root": root, "logo": mark, "footer": footer,
                  "body": text[meta.end():].replace("{root}", root).replace("{contact}", CONTACT).replace("{email}", EMAIL),
                  "nav": nav(section), "nav_label": name, "contact": CONTACT, "email": EMAIL, "css": css}
        page = LAYOUT
        for key, value in values.items():
            page = page.replace("{" + key + "}", value)
        page = re.sub(r'href="([^":#]*/)?index\.html', lambda m: 'href="' + (m.group(1) or "./"), page)  # folder addresses, no index.html
        (OUT / rel).parent.mkdir(parents=True, exist_ok=True)
        (OUT / rel).write_text(page, encoding="utf-8")
    for section in SECTIONS:
        for page in REMOVED:
            (OUT / section / page).write_text(redirect("./"), encoding="utf-8")
    for old, new in MOVED.items():
        (OUT / old).mkdir(exist_ok=True)
        for page in ["index.html", *REMOVED]:
            (OUT / old / page).write_text(redirect(f"../{new}/"), encoding="utf-8")
    print(f"built {OUT}")


if __name__ == "__main__":
    main()
