"""vidkit — Kommandozeile. Jeder Pipeline-Schritt ist ein eigener Befehl."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import default_style_path, load_style
from .paths import Project
from .util import die, log, set_verbose, step


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-p", "--project", default="default", help="Projektname (Ordner in projects/)")
    parser.add_argument("--style", type=Path, default=None, help="Pfad zu einer style.json")
    parser.add_argument("-v", "--verbose", action="store_true", help="ffmpeg-Kommandos zeigen")
    parser.add_argument("--no-hw", action="store_true", help="Hardware-Encoding aus (VideoToolbox)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vidkit",
        description="Lokale Short-Form-Ad-Pipeline: Rohvideo → geschnittenes 9:16-MP4.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Reihenfolge:  learn (optional) → ingest → transcribe → plan →\n"
            "              assets → sfx → stock (optional) → render\n"
            "Oder alles auf einmal:  vidkit all rohvideo.mp4 -p meinprojekt\n"
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("learn", help="Referenz-Ad ausmessen und style.json schreiben")
    _common(c)
    c.add_argument("reference", type=Path, help="Referenzvideo")
    c.add_argument("-o", "--out", type=Path, default=None, help="Ziel-style.json (Default: style.json)")
    c.add_argument("--fps-sample", type=float, default=2.0, help="Analyse-Abtastrate fuer OCR/Farbe")
    c.add_argument("--no-ocr", action="store_true", help="OCR ueberspringen (schneller)")
    c.add_argument("--merge", action="store_true", help="In bestehende style.json mergen statt neu schreiben")

    c = sub.add_parser("ingest", help="Rohvideo auf Zielformat/fps/Lautheit normalisieren")
    _common(c)
    c.add_argument("source", type=Path, help="Rohvideo")
    c.add_argument("--skip-loudnorm", action="store_true")

    c = sub.add_parser("transcribe", help="Transkript mit Wort-Timecodes (Deutsch)")
    _common(c)
    c.add_argument("--backend", default="auto", choices=["auto", "mlx", "faster", "openai"])
    c.add_argument("--model", default=None, help="Whisper-Modell (Default aus --backend)")
    c.add_argument("--language", default="de")
    c.add_argument("--import", dest="import_path", type=Path, default=None,
                   help="Fertiges Transkript uebernehmen statt Whisper laufen zu lassen")

    c = sub.add_parser("plan", help="Schnittplan edit.json aus Transkript + style.json bauen")
    _common(c)
    c.add_argument("--seed", type=int, default=None, help="Zufallsseed (reproduzierbar)")
    c.add_argument("--force", action="store_true", help="Bestehende edit.json ueberschreiben")

    c = sub.add_parser("assets", help="Overlays/Captions/Motion-Graphics als Alpha-Videos rendern")
    _common(c)
    c.add_argument("--only", default=None, help="Nur diese Element-IDs (Komma-getrennt)")
    c.add_argument("--kinds", default="captions,overlays,motion_graphics")
    c.add_argument("--force", action="store_true", help="Auch unveraenderte Elemente neu rendern")

    c = sub.add_parser("sfx", help="Sound-Effekte aus assets/sfx/ auf die Marker legen")
    _common(c)
    c.add_argument("--seed", type=int, default=None)
    c.add_argument("--reassign", action="store_true", help="Bereits gewaehlte Dateien neu wuerfeln")

    c = sub.add_parser("stock", help="B-Roll-Kandidaten von Pexels laden (Auswahl trifft der Mensch)")
    _common(c)
    c.add_argument("--per-slot", type=int, default=5)
    c.add_argument("--slot", default=None, help="Nur dieser Slot (ID)")
    c.add_argument("--key", default=None, help="Pexels-API-Key (sonst $PEXELS_API_KEY)")
    c.add_argument("--orientation", default="portrait",
                   choices=["portrait", "landscape", "square"])

    c = sub.add_parser("render", help="Alles zusammensetzen → MP4")
    _common(c)
    c.add_argument("-o", "--out", type=Path, default=None)
    c.add_argument("--preview", action="store_true", help="Niedrige Aufloesung, schnell")
    c.add_argument("--from-stage", default="base", choices=["base", "composite", "audio", "mux"],
                   help="Ab welcher Stufe neu gerendert wird")

    c = sub.add_parser("preview", help="Schnelle Vorschau in niedriger Aufloesung")
    _common(c)
    c.add_argument("-o", "--out", type=Path, default=None)

    c = sub.add_parser("serve", help="Lokale Weboberflaeche zum Bearbeiten der edit.json")
    _common(c)
    c.add_argument("--port", type=int, default=8777)
    c.add_argument("--host", default="127.0.0.1")
    c.add_argument("--open", action="store_true", help="Browser oeffnen")

    c = sub.add_parser("all", help="Komplette Kette in einem Befehl")
    _common(c)
    c.add_argument("source", type=Path)
    c.add_argument("--with-stock", action="store_true")
    c.add_argument("--transcript", type=Path, default=None,
                   help="Fertiges Transkript uebernehmen statt Whisper laufen zu lassen")
    c.add_argument("--preview", action="store_true")
    c.add_argument("--seed", type=int, default=None)

    c = sub.add_parser("doctor", help="Pruefen, welche Werkzeuge vorhanden sind")
    _common(c)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    set_verbose(getattr(args, "verbose", False))
    project = Project.open(args.project)
    hw = not getattr(args, "no_hw", False)

    if args.cmd == "doctor":
        from .doctor import doctor
        return doctor()

    style = load_style(args.style, project)
    from .ffmpeg import require_ffmpeg
    require_ffmpeg()

    if args.cmd == "ingest":
        from .ingest import ingest
        ingest(project, args.source, style, hw=hw, skip_loudnorm=args.skip_loudnorm)

    elif args.cmd == "transcribe":
        from .transcribe import transcribe
        transcribe(project, backend=args.backend, model=args.model, language=args.language,
                   import_path=args.import_path)

    elif args.cmd == "plan":
        from .plan import plan
        plan(project, style, seed=args.seed, force=args.force)

    elif args.cmd == "assets":
        from .assets import build_assets
        only = args.only.split(",") if args.only else None
        build_assets(project, style, kinds=args.kinds.split(","), only=only, force=args.force)

    elif args.cmd == "sfx":
        from .sfx import assign_sfx
        assign_sfx(project, style, seed=args.seed, reassign=args.reassign)

    elif args.cmd == "stock":
        from .stock import fetch_stock
        fetch_stock(project, per_slot=args.per_slot, slot=args.slot, key=args.key,
                    orientation=args.orientation)

    elif args.cmd == "render":
        from .render import render
        render(project, style, out=args.out, preview=args.preview, hw=hw,
               from_stage=args.from_stage)

    elif args.cmd == "preview":
        from .render import render
        render(project, style, out=args.out or project.preview_video, preview=True, hw=hw)

    elif args.cmd == "learn":
        from .learn import learn
        learn(args.reference, out=args.out or default_style_path(), fps_sample=args.fps_sample,
              ocr=not args.no_ocr, merge=args.merge)

    elif args.cmd == "serve":
        from .serve import serve
        serve(project, style, host=args.host, port=args.port, open_browser=args.open)

    elif args.cmd == "all":
        from .assets import build_assets
        from .ingest import ingest
        from .plan import plan
        from .render import render
        from .sfx import assign_sfx
        from .transcribe import transcribe
        ingest(project, args.source, style, hw=hw)
        transcribe(project, import_path=args.transcript)
        plan(project, style, seed=args.seed, force=True)
        if args.with_stock:
            from .stock import fetch_stock
            fetch_stock(project)
            step("Stock-Kandidaten liegen bereit — waehle aus und starte 'vidkit render'.")
            return 0
        build_assets(project, style)
        assign_sfx(project, style, seed=args.seed)
        render(project, style, preview=args.preview, hw=hw)
    else:
        die(f"Unbekannter Befehl: {args.cmd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
