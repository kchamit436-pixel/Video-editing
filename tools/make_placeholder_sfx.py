#!/usr/bin/env python3
"""Erzeugt eine Platzhalter-SFX-Bibliothek unter assets/sfx/.

Alles hier ist mit ffmpeg synthetisiert — nichts heruntergeladen, nichts aus
fremden Videos kopiert. Die Dateien sind bewusst schlicht: sie machen die
Pipeline testbar. Ersetze sie durch deine eigene Bibliothek, die Ordnerstruktur
bleibt dieselbe.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SFX = ROOT / "assets" / "sfx"
SR = 48000

# (Kategorie, Name, ffmpeg-lavfi-Quelle, Dauer, Nachbearbeitung)
RECIPES: list[tuple[str, str, str, float, str]] = [
    ("whoosh", "whoosh_up_a", f"anoisesrc=c=pink:r={SR}:a=0.5", 0.45,
     "highpass=f=300,lowpass=f=6000,volume='0.9*between(t,0,0.45)*sin(3.14159*t/0.45)':eval=frame,"
     "aformat=channel_layouts=stereo,areverse,afade=t=in:d=0.05,areverse"),
    ("whoosh", "whoosh_up_b", f"anoisesrc=c=white:r={SR}:a=0.4", 0.35,
     "highpass=f=600,lowpass=f=9000,volume='0.85*pow(t/0.35,0.6)*(1-t/0.35)*3':eval=frame,"
     "aformat=channel_layouts=stereo"),
    ("whoosh", "whoosh_soft", f"anoisesrc=c=brown:r={SR}:a=0.6", 0.55,
     "highpass=f=150,lowpass=f=3500,volume='0.8*sin(3.14159*t/0.55)':eval=frame,"
     "aformat=channel_layouts=stereo"),
    ("transition", "swipe_a", f"anoisesrc=c=pink:r={SR}:a=0.5", 0.30,
     "highpass=f=800,lowpass=f=7000,volume='0.9*(1-t/0.30)':eval=frame,"
     "aformat=channel_layouts=stereo"),
    ("transition", "swipe_b", f"sine=frequency=180:r={SR}:beep_factor=0", 0.28,
     "asetrate=48000,atempo=1,volume='0.7*(1-t/0.28)':eval=frame,"
     "highpass=f=120,aformat=channel_layouts=stereo"),
    ("pop", "pop_a", f"sine=frequency=900:r={SR}", 0.10,
     "volume='0.9*exp(-28*t)':eval=frame,aformat=channel_layouts=stereo"),
    ("pop", "pop_b", f"sine=frequency=1250:r={SR}", 0.09,
     "volume='0.85*exp(-32*t)':eval=frame,aformat=channel_layouts=stereo"),
    ("pop", "pop_c", f"sine=frequency=680:r={SR}", 0.12,
     "volume='0.9*exp(-24*t)':eval=frame,aformat=channel_layouts=stereo"),
    ("click", "click_a", f"anoisesrc=c=white:r={SR}:a=0.7", 0.05,
     "highpass=f=1800,volume='0.8*exp(-70*t)':eval=frame,aformat=channel_layouts=stereo"),
    ("click", "click_b", f"anoisesrc=c=white:r={SR}:a=0.6", 0.04,
     "highpass=f=2600,volume='0.75*exp(-90*t)':eval=frame,aformat=channel_layouts=stereo"),
    ("impact", "impact_a", f"anoisesrc=c=brown:r={SR}:a=0.9", 0.40,
     "lowpass=f=900,volume='0.95*exp(-9*t)':eval=frame,aformat=channel_layouts=stereo"),
    ("impact", "impact_b", f"sine=frequency=70:r={SR}", 0.45,
     "volume='0.95*exp(-7*t)':eval=frame,aformat=channel_layouts=stereo"),
    ("sub", "sub_drop", f"sine=frequency=48:r={SR}", 0.70,
     "volume='0.9*exp(-4*t)':eval=frame,lowpass=f=140,aformat=channel_layouts=stereo"),
    ("sub", "sub_hit", f"sine=frequency=60:r={SR}", 0.50,
     "volume='0.9*exp(-6*t)':eval=frame,lowpass=f=160,aformat=channel_layouts=stereo"),
    ("riser", "riser_short", f"anoisesrc=c=pink:r={SR}:a=0.5", 0.90,
     "highpass=f=400,volume='0.75*pow(t/0.9,2)':eval=frame,aformat=channel_layouts=stereo"),
    ("riser", "riser_long", f"anoisesrc=c=white:r={SR}:a=0.4", 1.40,
     "highpass=f=250,volume='0.7*pow(t/1.4,2.2)':eval=frame,aformat=channel_layouts=stereo"),
]


def main() -> int:
    made = 0
    for category, name, source, dur, chain in RECIPES:
        out_dir = SFX / category
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{name}.wav"
        proc = subprocess.run([
            "ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"{source}:d={dur}", "-t", str(dur),
            "-af", chain + ",afade=t=out:st=" + str(max(0.0, dur - 0.02)) + ":d=0.02",
            "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(out),
        ], capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"! {category}/{name}: {proc.stderr.strip()[-200:]}", file=sys.stderr)
            continue
        made += 1
    print(f"{made}/{len(RECIPES)} Platzhalter-Sounds in {SFX}")
    for d in sorted(SFX.iterdir()):
        if d.is_dir():
            print(f"  {d.name}/  {len(list(d.glob('*.wav')))} Dateien")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
