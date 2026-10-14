#!/usr/bin/env python3
"""Local edit mode: serves site/ with an inline text editor.

Every element with a data-en attribute becomes editable. Saving writes the
German text (element content) or the English text (data-en) back into the
HTML source and leaves the rest of the file untouched.

    python3 tools/edit.py [port]   # then open http://127.0.0.1:8359/
"""
import json
import re
import sys
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
SITE = TOOLS.parent / "site"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
INJECT = '<link rel="stylesheet" href="/__edit/edit.css"><script src="/__edit/edit.js" defer></script>'


class Locator(HTMLParser):
    """Finds the source offsets of every element with data-en, in document order."""

    def __init__(self, src):
        super().__init__(convert_charrefs=True)
        self.lines = [0]
        for line in src.splitlines(keepends=True):
            self.lines.append(self.lines[-1] + len(line))
        self.found, self.open = [], []
        self.feed(src)
        self.close()

    def position(self):
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def handle_starttag(self, tag, attrs):
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


def save(page, index, tag, lang, html):
    path = (SITE / page.lstrip("/")).resolve()
    if path.is_dir():
        path = path / "index.html"
    if SITE not in path.parents or path.suffix != ".html":
        raise ValueError("bad path")
    src = path.read_text(encoding="utf-8")
    el = Locator(src).found[index]
    if el["tag"] != tag:
        raise ValueError(f"element {index} is <{el['tag']}>, expected <{tag}>")
    if lang == "en":
        value = html.replace("&", "&amp;").replace('"', "&quot;")
        start_tag = src[el["start"]:el["inner"]]
        new_tag, n = re.subn(r'(\sdata-en=)"[^"]*"', lambda m: f'{m[1]}"{value}"', start_tag, count=1)
        if n != 1:
            raise ValueError("data-en attribute not found")
        src = src[:el["start"]] + new_tag + src[el["inner"]:]
    else:
        src = src[:el["inner"]] + html + src[el["end"]:]
    path.write_text(src, encoding="utf-8")


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        route = self.path.split("?")[0]
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
        if self.path != "/__edit/save":
            return self.send(404, b"not found", "text/plain")
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        try:
            save(data["page"], data["index"], data["tag"], data["lang"], data["html"])
        except (ValueError, IndexError, KeyError) as e:
            return self.send(409, str(e).encode(), "text/plain")
        self.send(200, b"ok", "text/plain")

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
