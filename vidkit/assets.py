"""Schritt 4: Text-Overlays, Captions und Motion Graphics als Videos mit Alphakanal.

HTML/CSS im headless Chromium, Bild fuer Bild abfotografiert, als qtrle-MOV mit
Alpha gespeichert. Bewusst kein ffmpeg-drawtext: nur so gibt es echte
Typografie, Easing und Overshoot.

Jedes Element wird einzeln gerendert und in assets/manifest.json mit einem Hash
vermerkt — unveraenderte Elemente werden beim naechsten Lauf uebersprungen.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from .config import Style
from .editdoc import elements, load_edit
from .ffmpeg import alpha_encoder_args
from .paths import Project, repo_root
from .util import die, ok, read_json, step, warn, write_json

TEMPLATE = Path(__file__).parent / "templates" / "element.html"
TEMPLATE_VERSION = 3          # hochzaehlen, wenn sich das Template aendert
KINDS = ("captions", "overlays", "motion_graphics")
_FONT_MIME = {".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf",
              ".otf": "font/otf"}


def _font_css(style: Style) -> str:
    """Lokale Schriftdateien als data:-URI einbetten (Chromium laedt nichts nach)."""
    css = []
    for entry in style.get("typography.font_files", []) or []:
        if isinstance(entry, str):
            entry = {"file": entry}
        path = Path(entry["file"])
        if not path.is_absolute():
            path = repo_root() / path
        if not path.exists():
            warn(f"Schriftdatei fehlt: {path}")
            continue
        mime = _FONT_MIME.get(path.suffix.lower(), "font/ttf")
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        css.append(
            "@font-face{{font-family:{fam};font-weight:{w};font-style:{s};"
            "src:url(data:{mime};base64,{b64});}}".format(
                fam=json.dumps(entry.get("family", "Custom")), w=entry.get("weight", "400"),
                s=entry.get("style", "normal"), mime=mime, b64=b64)
        )
    return "".join(css)


def _payload(kind: str, element: dict, style: Style) -> dict[str, Any]:
    return {
        "kind": kind,
        "element": element,
        "style": style.section(kind),
        "typography": style.section("typography"),
        "safe_zones": style.section("safe_zones"),
        "frame": {"width": style.width, "height": style.height, "fps": style.fps},
    }


def _hash(payload: dict, font_css: str) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False) + font_css
    return hashlib.sha1(f"v{TEMPLATE_VERSION}|{blob}".encode("utf-8")).hexdigest()[:16]


def _tail_seconds(kind: str, style: Style) -> float:
    """Auslaufanimation braucht Frames ueber t_out hinaus."""
    return float(style.get(f"{kind}.animation.out_duration", 0.0) or 0.0)


def _chromium_kwargs() -> dict:
    exe = os.environ.get("VIDKIT_CHROMIUM_PATH")
    return {"executable_path": exe} if exe else {}


def stale_elements(project: Project, style: Style, doc: dict) -> list[str]:
    """IDs der Elemente, deren gerendertes Asset nicht mehr zum Plan passt."""
    if not project.assets_manifest.exists():
        return [e["id"] for k in KINDS for e in elements(doc, k)]
    manifest = read_json(project.assets_manifest).get("elements", {})
    font_css = _font_css(style)
    out = []
    for kind in KINDS:
        for el in elements(doc, kind):
            info = manifest.get(el["id"])
            if not info or info.get("hash") != _hash(_payload(kind, el, style), font_css):
                out.append(el["id"])
    return out


def build_assets(project: Project, style: Style, *, kinds: list[str] | None = None,
                 only: list[str] | None = None, force: bool = False) -> Path:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        die("playwright fehlt:  pip install playwright && playwright install chromium")

    doc = load_edit(project)
    kinds = [k for k in (kinds or KINDS) if k in KINDS]
    project.assets_dir.mkdir(parents=True, exist_ok=True)
    manifest = ({} if force else
                (read_json(project.assets_manifest) if project.assets_manifest.exists() else {}))
    manifest.setdefault("elements", {})

    fps = style.fps
    font_css = _font_css(style)

    jobs: list[tuple[str, dict, dict, str]] = []
    for kind in kinds:
        for el in elements(doc, kind):
            if only and el["id"] not in only:
                continue
            payload = _payload(kind, el, style)
            jobs.append((kind, el, payload, _hash(payload, font_css)))

    if not jobs:
        warn("Keine Elemente zu rendern.")
        write_json(project.assets_manifest, manifest)
        return project.assets_manifest

    todo = [j for j in jobs
            if force or manifest["elements"].get(j[1]["id"], {}).get("hash") != j[3]
            or not (project.root / manifest["elements"].get(j[1]["id"], {}).get("file", "x")).exists()]
    skipped = len(jobs) - len(todo)
    step(f"Assets: {len(jobs)} Elemente ({', '.join(kinds)}), "
         f"{len(todo)} zu rendern, {skipped} unveraendert")
    if not todo:
        ok("Alles aktuell.")
        return project.assets_manifest

    t0 = time.time()
    total_frames = 0
    template_html = TEMPLATE.read_text(encoding="utf-8")
    # Pro Element eine echte HTML-Datei: laesst sich zum Nachsehen im Browser oeffnen.
    html_dir = project.assets_dir / "_html"
    html_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(args=["--force-color-profile=srgb",
                                               "--disable-lcd-text"], **_chromium_kwargs())
        except Exception as exc:  # noqa: BLE001
            die("Chromium laesst sich nicht starten:\n"
                f"  {str(exc).splitlines()[0]}\n"
                "  Abhilfe:  playwright install chromium\n"
                "  Oder eine vorhandene Installation nutzen:\n"
                "    export VIDKIT_CHROMIUM_PATH=/pfad/zu/chrome")
        page = browser.new_page(viewport={"width": style.width, "height": style.height},
                                device_scale_factor=1)
        for kind, el, payload, h in todo:
            dur = float(el["t_out"]) - float(el["t_in"]) + _tail_seconds(kind, style)
            n_frames = max(1, int(math.ceil(dur * fps)))
            html_file = html_dir / f"{el['id']}.html"
            inject = (f"<style>{font_css}</style>" if font_css else "") + \
                "<script>window.VIDKIT = " + \
                json.dumps(payload, ensure_ascii=False) + ";</script>"
            html_file.write_text(template_html.replace("<!--VIDKIT_INJECT-->", inject),
                                 encoding="utf-8")
            page.goto(html_file.resolve().as_uri())
            page.wait_for_function("window.vidkitReady === true", timeout=15000)

            samples = [i / fps for i in range(n_frames)]
            box = page.evaluate("(s) => window.vidkitBounds(s)", samples)
            pad = 4
            if box:
                x = max(0, int(box["x"]) - pad)
                y = max(0, int(box["y"]) - pad)
                w = min(style.width - x, int(math.ceil(box["width"])) + 2 * pad)
                h_ = min(style.height - y, int(math.ceil(box["height"])) + 2 * pad)
            else:
                x = y = 0
                w, h_ = style.width, style.height
            w = max(2, w - (w % 2)); h_ = max(2, h_ - (h_ % 2))
            clip = {"x": x, "y": y, "width": w, "height": h_}

            out_file = project.assets_dir / f"{el['id']}.mov"
            proc = subprocess.Popen(
                ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
                 "-f", "image2pipe", "-framerate", str(fps), "-i", "-",
                 *alpha_encoder_args(), "-r", str(fps), str(out_file)],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            assert proc.stdin is not None
            for i in range(n_frames):
                page.evaluate("(t) => window.vidkitRender(t)", i / fps)
                proc.stdin.write(page.screenshot(omit_background=True, clip=clip, type="png"))
            proc.stdin.close()
            err = proc.stderr.read().decode() if proc.stderr else ""
            if proc.wait() != 0:
                die(f"Asset {el['id']} konnte nicht kodiert werden:\n{err[-600:]}")
            total_frames += n_frames

            manifest["elements"][el["id"]] = {
                "id": el["id"], "kind": kind, "hash": h,
                "file": str(out_file.relative_to(project.root)),
                "t_in": float(el["t_in"]), "t_out": round(float(el["t_in"]) + dur, 3),
                "x": x, "y": y, "width": w, "height": h_, "frames": n_frames,
            }
        browser.close()

    manifest["template_version"] = TEMPLATE_VERSION
    manifest["frame"] = {"width": style.width, "height": style.height, "fps": fps}
    write_json(project.assets_manifest, manifest)
    took = time.time() - t0
    ok(f"{len(todo)} Assets, {total_frames} Frames in {took:.1f}s "
       f"({total_frames / took:.0f} Frames/s) → {project.assets_dir}")
    return project.assets_manifest
