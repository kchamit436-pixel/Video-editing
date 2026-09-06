"""'vidkit doctor' — zeigt, welche Werkzeuge vorhanden sind und was fehlt."""
from __future__ import annotations

import importlib
import platform
import shutil
import sys


CHECKS_BIN = [
    ("ffmpeg", "brew install ffmpeg", True),
    ("ffprobe", "brew install ffmpeg", True),
    ("tesseract", "brew install tesseract tesseract-lang (nur fuer 'learn')", False),
]

CHECKS_PY = [
    ("numpy", "pip install numpy", True),
    ("cv2", "pip install opencv-python", False),
    ("scenedetect", "pip install scenedetect", False),
    ("playwright", "pip install playwright && playwright install chromium", False),
    ("mlx_whisper", "pip install mlx-whisper (Apple Silicon, schnellster Weg)", False),
    ("faster_whisper", "pip install faster-whisper", False),
    ("easyocr", "pip install easyocr (Alternative zu tesseract)", False),
    ("pytesseract", "pip install pytesseract", False),
    ("PIL", "pip install pillow", False),
    ("requests", "pip install requests (nur fuer 'stock')", False),
]


def doctor() -> int:
    print(f"System : {platform.system()} {platform.machine()}  Python {sys.version.split()[0]}")
    missing_required = 0
    print("\nProgramme:")
    for name, hint, required in CHECKS_BIN:
        path = shutil.which(name)
        mark = "✓" if path else ("✗" if required else "–")
        print(f"  {mark} {name:16s} {path or hint}")
        if required and not path:
            missing_required += 1

    print("\nPython-Pakete:")
    for name, hint, required in CHECKS_PY:
        try:
            importlib.import_module(name)
            print(f"  ✓ {name:16s}")
        except Exception:  # noqa: BLE001
            print(f"  {'✗' if required else '–'} {name:16s} {hint}")
            if required:
                missing_required += 1

    try:
        from .ffmpeg import has_encoder, is_apple_silicon
        print("\nEncoder:")
        print(f"  {'✓' if has_encoder('h264_videotoolbox') else '–'} h264_videotoolbox "
              f"(Hardware-Encoding{' — aktiv' if is_apple_silicon() else ''})")
        print(f"  {'✓' if has_encoder('libx264') else '✗'} libx264 (Fallback)")
        print(f"  {'✓' if has_encoder('qtrle') else '–'} qtrle (Overlays mit Alphakanal)")
    except Exception as exc:  # noqa: BLE001
        print(f"  Encoder-Pruefung fehlgeschlagen: {exc}")

    import os
    exe = os.environ.get("VIDKIT_CHROMIUM_PATH")
    if exe:
        print(f"\nVIDKIT_CHROMIUM_PATH={exe}")

    print("\n" + ("Alles Noetige da." if missing_required == 0
                  else f"{missing_required} Pflicht-Abhaengigkeit(en) fehlen."))
    return 0 if missing_required == 0 else 1
