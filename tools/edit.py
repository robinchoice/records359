#!/usr/bin/env python3
"""Local edit mode: serves site/ with an inline text editor.

Every element with a data-en attribute becomes editable. Saving writes the
German text (element content) or the English text (data-en) back into the
HTML source and leaves the rest of the file untouched. Images can be swapped
for another one from site/img or a new upload, which is converted to WebP in
700 and 1400 px. The top-level blocks of <main> can be moved up, moved down
or deleted; nav links and section numbers follow.

    python3 tools/edit.py [port]   # then open http://127.0.0.1:8359/
"""
import io
import json
import re
import unicodedata
import sys
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageOps

TOOLS = Path(__file__).resolve().parent
SITE = TOOLS.parent / "site"
IMG = SITE / "img"
SIZES = (700, 1400)
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
INJECT = '<link rel="stylesheet" href="/__edit/edit.css"><script src="/__edit/edit.js" defer></script>'


class Locator(HTMLParser):
    """Finds the source offsets of every element with data-en and every img, in document order."""

    def __init__(self, src):
        super().__init__(convert_charrefs=True)
        self.lines = [0]
        for line in src.splitlines(keepends=True):
            self.lines.append(self.lines[-1] + len(line))
        self.found, self.open, self.images = [], [], []
        self.feed(src)
        self.close()

    def position(self):
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            start = self.position()
            self.images.append({"start": start, "inner": start + len(self.get_starttag_text())})
        for el in self.open:
            if el["tag"] == tag:
                el["depth"] += 1
        if any(name == "data-en" for name, _ in attrs) and tag not in VOID:
            start = self.position()
            el = {"tag": tag, "start": start, "inner": start + len(self.get_starttag_text()), "depth": 0}
            self.found.append(el)
            self.open.append(el)

    def handle_endtag(self, tag):
        for el in list(self.open):
            if el["tag"] != tag:
                continue
            if el["depth"]:
                el["depth"] -= 1
            else:
                el["end"] = self.position()
                self.open.remove(el)


def page_file(page):
    path = (SITE / page.lstrip("/")).resolve()
    if path.is_dir():
        path = path / "index.html"
    if SITE not in path.parents or path.suffix != ".html":
        raise ValueError("bad path")
    return path


def attr(value):
    return value.replace("&", "&amp;").replace('"', "&quot;")


def set_attr(tag, name, value):
    new, n = re.subn(rf'(\s{name}=)"[^"]*"', lambda m: f'{m[1]}"{attr(value)}"', tag, count=1)
    if n != 1:
        raise ValueError(f"{name} attribute not found")
    return new


def save(page, index, tag, lang, html):
    path = page_file(page)
    src = path.read_text(encoding="utf-8")
    el = Locator(src).found[index]
    if el["tag"] != tag:
        raise ValueError(f"element {index} is <{el['tag']}>, expected <{tag}>")
    if lang == "en":
        src = src[:el["start"]] + set_attr(src[el["start"]:el["inner"]], "data-en", html) + src[el["inner"]:]
    else:
        src = src[:el["inner"]] + html + src[el["end"]:]
    path.write_text(src, encoding="utf-8")


def images():
    return sorted(p.name[:-9] for p in IMG.glob("*-700.webp") if (IMG / f"{p.name[:-9]}-1400.webp").exists())


def upload(name, data):
    slug = unicodedata.normalize("NFKD", Path(name).stem).encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-") or "bild"
    base, n = slug, 2
    while (IMG / f"{base}-700.webp").exists():
        base, n = f"{slug}-{n}", n + 1
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    for size in SIZES:
        copy = im.copy()
        copy.thumbnail((size, size * 10), Image.LANCZOS)
        copy.save(IMG / f"{base}-{size}.webp", quality=82, method=6)
    return base


def swap(page, index, base, alt, alt_en):
    if base not in images():
        raise ValueError(f"unknown image {base}")
    path = page_file(page)
    src = path.read_text(encoding="utf-8")
    img = Locator(src).images[index]
    tag = src[img["start"]:img["inner"]]
    old = re.search(r'\ssrc="/img/(.+)-(?:700|1400)\.webp"', tag)
    if not old:
        raise ValueError("this image cannot be swapped")
    old = f"/img/{old[1]}-"
    tag = tag.replace(old, f"/img/{base}-")
    width = re.search(r'\swidth="(\d+)"', tag)
    if width:
        w, h = Image.open(IMG / f"{base}-1400.webp").size
        tag = set_attr(tag, "height", str(round(int(width[1]) * h / w)))
    tag = set_attr(set_attr(tag, "alt", alt), "data-en-alt", alt_en)
    # Gallery images link to their large version.
    link = re.search(r'<a [^>]*>\s*$', src[:img["start"]])
    start = link.start() if link and old in link[0] else img["start"]
    src = src[:start] + src[start:img["start"]].replace(old, f"/img/{base}-") + tag + src[img["inner"]:]
    path.write_text(src, encoding="utf-8")


def blocks(src):
    """Splits a page at its top-level <main> blocks, which start on unindented lines."""
    head, rest = src.split("<main>\n", 1)
    body, tail = rest.split("\n</main>", 1)
    starts = [m.start() for m in re.finditer(r"^<(?!/)", body, re.M)]
    parts = [body[a:b].rstrip() for a, b in zip(starts, starts[1:] + [len(body)])]
    return head + "<main>\n", parts, "\n</main>" + tail


def section_id(part):
    m = re.match(r'<\w+[^>]*\sid="([^"]+)"', part)
    return m and m[1]


def arrange(page, index, ref, action):
    path = page_file(page)
    head, parts, tail = blocks(path.read_text(encoding="utf-8"))
    if ref not in parts[index].split("\n", 1)[0]:
        raise ValueError("the page changed, please reload")
    note = ""
    if action in ("up", "down"):
        other = index - 1 if action == "up" else index + 1
        if not 0 <= other < len(parts):
            raise ValueError("already at the edge")
        parts[index], parts[other] = parts[other], parts[index]
    elif action == "delete":
        sid = section_id(parts.pop(index))
        if sid:
            head = re.sub(rf'\n[ \t]*<a href="#{re.escape(sid)}"[^\n]*', "", head)
            left = "".join(parts).count(f'href="#{sid}"')
            if left:
                note = f"{left} Link(s) zeigen noch auf #{sid}"
    else:
        raise ValueError(f"unknown action {action}")
    # Header nav follows the section order; links with a class (CTA buttons) stay put.
    order = [sid for sid in map(section_id, parts) if sid]
    nav = re.search(r'<nav class="nav" id="nav">.*?</nav>', head, re.S)
    if nav:
        lines = nav[0].split("\n")
        ids = {i: m[1] for i, line in enumerate(lines)
               if (m := re.fullmatch(r'\s*<a href="#([\w-]+)" data-en=.*', line)) and m[1] in order}
        for i, line in zip(ids, sorted((lines[i] for i in ids), key=lambda l: order.index(re.search(r'#([\w-]+)', l)[1]))):
            lines[i] = line
        head = head[:nav.start()] + "\n".join(lines) + head[nav.end():]
    numbers = iter(range(1, 100))
    body = re.sub(r'<span class="num">\d+</span>', lambda m: f'<span class="num">{next(numbers)}</span>', "\n\n".join(parts))
    path.write_text(head + body + tail, encoding="utf-8")
    return note


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        route = self.path.split("?")[0]
        if route == "/__edit/images":
            return self.send(200, json.dumps(images()).encode(), "application/json")
        if route.startswith("/__edit/"):
            file = TOOLS / ("edit" + Path(route).suffix)
            return self.send(200, file.read_bytes(), "text/css" if file.suffix == ".css" else "text/javascript")
        local = Path(self.translate_path(route))
        if local.is_dir():
            local = local / "index.html"
        if local.suffix == ".html" and local.is_file():
            body = local.read_text(encoding="utf-8").replace("</body>", INJECT + "</body>", 1)
            return self.send(200, body.encode(), "text/html; charset=utf-8")
        super().do_GET()

    def do_POST(self):
        url = urlparse(self.path)
        body = self.rfile.read(int(self.headers["Content-Length"]))
        try:
            if url.path == "/__edit/save":
                data = json.loads(body)
                save(data["page"], data["index"], data["tag"], data["lang"], data["html"])
                return self.send(200, b"ok", "text/plain")
            if url.path == "/__edit/upload":
                base = upload(parse_qs(url.query)["name"][0], body)
                return self.send(200, json.dumps(base).encode(), "application/json")
            if url.path == "/__edit/arrange":
                data = json.loads(body)
                note = arrange(data["page"], data["index"], data["ref"], data["action"])
                return self.send(200, note.encode(), "text/plain")
            if url.path == "/__edit/image":
                data = json.loads(body)
                swap(data["page"], data["index"], data["base"], data["alt"], data["altEn"])
                return self.send(200, b"ok", "text/plain")
        except (ValueError, IndexError, KeyError, OSError) as e:
            return self.send(409, str(e).encode(), "text/plain")
        self.send(404, b"not found", "text/plain")

    def send(self, status, body, ctype):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8359
    print(f"Edit mode: http://127.0.0.1:{port}/  (Klanglabor: /klanglabor/)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(SITE))).serve_forever()
