"""Schritt 8: Lokale Weboberflaeche zum Bearbeiten der edit.json.

Ein kleiner Server aus der Standardbibliothek, eine HTML-Seite, kein Framework.
Bindet standardmaessig nur an 127.0.0.1 — nichts geht ins Netz, keine Anmeldung.
"""
from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import Style
from .editdoc import ELEMENT_KINDS, SCHEMA_VERSION, load_edit, save_edit, sort_all
from .edits import delete_range, delete_segment, split_segment, trim_segment
from .paths import Project, repo_root
from .util import log, ok, step, warn

WEB = Path(__file__).parent / "web"


class RenderJob:
    """Laeuft in einem Thread, damit die Oberflaeche waehrenddessen bedienbar bleibt."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.lines: list[str] = []
        self.running = False
        self.returncode: int | None = None
        self.lock = threading.Lock()

    def start(self, steps: list[list[str]], cwd: Path) -> bool:
        """Mehrere Befehle nacheinander. Bricht ab, sobald einer fehlschlaegt."""
        if steps and isinstance(steps[0], str):      # Bequemlichkeit: ein einzelner Befehl
            steps = [steps]                          # type: ignore[list-item]
        with self.lock:
            if self.running:
                return False
            self.running = True
            self.returncode = None
            self.lines = []
        def run() -> None:
            code = 0
            try:
                for args in steps:
                    with self.lock:
                        self.lines.append(f"$ {' '.join(args)}")
                    self.proc = subprocess.Popen(args, cwd=str(cwd), stdout=subprocess.PIPE,
                                                 stderr=subprocess.STDOUT, text=True, bufsize=1)
                    assert self.proc.stdout is not None
                    for line in self.proc.stdout:
                        with self.lock:
                            self.lines.append(line.rstrip("\n"))
                            if len(self.lines) > 400:
                                self.lines = self.lines[-400:]
                    self.proc.wait()
                    code = self.proc.returncode
                    if code != 0:
                        break
                self.returncode = code
            except Exception as exc:  # noqa: BLE001
                with self.lock:
                    self.lines.append(f"Fehler: {exc}")
                self.returncode = 1
            finally:
                self.running = False
        threading.Thread(target=run, daemon=True).start()
        return True

    def state(self) -> dict:
        with self.lock:
            return {"running": self.running, "returncode": self.returncode,
                    "lines": list(self.lines)}


def _video_for(project: Project) -> tuple[Path | None, str]:
    for path, label in ((project.preview_video, "preview.mp4"),
                        (project.out_video, "out.mp4"),
                        (project.render_dir / "composite.mp4", "render/composite.mp4"),
                        (project.base_video, "render/base.mp4")):
        if path.exists():
            return path, label
    if project.ingest_video.exists():
        return project.ingest_video, "ingest.mp4 (ungeschnitten — Zeiten weichen ab)"
    return None, "keins"


def make_handler(project: Project, style: Style, job: RenderJob):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # noqa: A003
            pass

        # -- Antworten --------------------------------------------------------
        def _send(self, code: int, body: bytes, ctype: str,
                  extra: dict | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, data, code: int = 200) -> None:
            self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _file(self, path: Path) -> None:
            ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            data = path.read_bytes()
            self._send(200, data, ctype)

        def _stream(self, path: Path) -> None:
            """Mit Range-Unterstuetzung — sonst laesst sich im Video nicht springen."""
            size = path.stat().st_size
            ctype = mimetypes.guess_type(path.name)[0] or "video/mp4"
            rng = self.headers.get("Range")
            if not rng or not rng.startswith("bytes="):
                with open(path, "rb") as fh:
                    self._send(200, fh.read(), ctype, {"Accept-Ranges": "bytes"})
                return
            spec = rng.split("=", 1)[1].split(",")[0]
            start_s, _, end_s = spec.partition("-")
            start = int(start_s) if start_s else 0
            end = int(end_s) if end_s else size - 1
            start = max(0, min(start, size - 1))
            end = max(start, min(end, size - 1))
            with open(path, "rb") as fh:
                fh.seek(start)
                chunk = fh.read(end - start + 1)
            self.send_response(206)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(len(chunk)))
            self.end_headers()
            self.wfile.write(chunk)

        # -- Routen -----------------------------------------------------------
        def do_GET(self) -> None:  # noqa: N802
            url = urlparse(self.path)
            route = url.path
            if route in ("/", "/index.html"):
                return self._file(WEB / "index.html")
            if route in ("/app.js", "/app.css"):
                return self._file(WEB / route.lstrip("/"))
            if route == "/api/edit":
                try:
                    return self._json(load_edit(project))
                except SystemExit:
                    return self._json({"error": "edit.json fehlt — erst 'vidkit plan' laufen "
                                                "lassen."}, 404)
            if route == "/api/style":
                return self._json(style.data)
            if route == "/api/info":
                video, label = _video_for(project)
                return self._json({
                    "project": project.name,
                    "video": "/media/video" if video else None,
                    "video_label": label,
                    "style_file": str(style.path),
                    "edit_file": str(project.edit),
                    "kinds": list(ELEMENT_KINDS),
                    "assets_built": project.assets_manifest.exists(),
                })
            if route == "/api/render/status":
                return self._json(job.state())
            if route == "/media/video":
                video, _ = _video_for(project)
                if not video:
                    return self._json({"error": "kein Video vorhanden"}, 404)
                return self._stream(video)
            return self._json({"error": "unbekannte Route"}, 404)

        def do_HEAD(self) -> None:  # noqa: N802
            self.do_GET()

        def do_POST(self) -> None:  # noqa: N802
            url = urlparse(self.path)
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            if url.path == "/api/edit":
                try:
                    doc = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError as exc:
                    return self._json({"error": f"kein gueltiges JSON: {exc}"}, 400)
                if doc.get("schema_version") != SCHEMA_VERSION:
                    return self._json({"error": "falsche schema_version"}, 400)
                save_edit(project, sort_all(doc))
                return self._json({"saved": True, "path": str(project.edit)})
            if url.path == "/api/segments":
                # Schneiden: Passage wegwerfen, teilen, kuerzen. Die Logik liegt
                # in edits.py, damit sie testbar ist und nicht im Browser haengt.
                try:
                    req = json.loads(raw.decode("utf-8") or "{}")
                except json.JSONDecodeError as exc:
                    return self._json({"error": f"kein gueltiges JSON: {exc}"}, 400)
                doc = load_edit(project)
                action = req.get("action")
                try:
                    if action == "delete":
                        stats = delete_segment(doc, req["id"])
                    elif action == "split":
                        stats = split_segment(doc, req["id"], float(req["t"]))
                    elif action == "trim":
                        stats = trim_segment(doc, req["id"],
                                             source_in=req.get("source_in"),
                                             source_out=req.get("source_out"))
                    elif action == "delete_range":
                        stats = delete_range(doc, float(req["t_in"]), float(req["t_out"]))
                    else:
                        return self._json({"error": f"unbekannte Aktion: {action}"}, 400)
                except (ValueError, KeyError) as exc:
                    return self._json({"error": str(exc)}, 400)
                save_edit(project, doc)
                return self._json({"ok": True, "stats": stats, "doc": doc})

            if url.path == "/api/render":
                opts = json.loads(raw.decode("utf-8") or "{}")
                args = [sys.executable, "-m", "vidkit", "render", "-p", project.name]
                if opts.get("preview", True):
                    args.append("--preview")
                stage = opts.get("from_stage")
                if stage:
                    args += ["--from-stage", stage]
                # Veraltete Overlays vorher neu bauen — sonst stehen sie nach
                # einem Schnitt an der falschen Stelle oder fehlen ganz.
                steps = []
                try:
                    from .assets import stale_elements
                    if stale_elements(project, style, load_edit(project)):
                        steps.append([sys.executable, "-m", "vidkit", "assets",
                                      "-p", project.name])
                except Exception:  # noqa: BLE001
                    pass
                steps.append(args)
                return self._json({"started": job.start(steps, repo_root())})
            if url.path == "/api/assets":
                args = [sys.executable, "-m", "vidkit", "assets", "-p", project.name]
                return self._json({"started": job.start([args], repo_root())})
            return self._json({"error": "unbekannte Route"}, 404)

    return Handler


def serve(project: Project, style: Style, *, host: str = "127.0.0.1", port: int = 8777,
          open_browser: bool = False) -> None:
    if not project.edit.exists():
        warn(f"{project.edit} fehlt — die Oberflaeche startet, zeigt aber nichts zu bearbeiten.")
    job = RenderJob()
    server = ThreadingHTTPServer((host, port), make_handler(project, style, job))
    video, label = _video_for(project)
    url = f"http://{host}:{port}/"
    step(f"Oberflaeche laeuft auf {url}  (Projekt '{project.name}', Video: {label})")
    log("   Beenden mit Strg-C.")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        ok("Oberflaeche beendet.")
