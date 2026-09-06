"""Schritt 0: Referenz-Ad ausmessen und daraus eine style.json schreiben.

Wichtig: es werden ausschliesslich Werte gemessen. Es wird kein Bild, kein Ton
und keine Grafik aus dem Referenzvideo uebernommen.
"""
from __future__ import annotations

import copy
import datetime as _dt
import json
from pathlib import Path

from .analyze import color as A_color
from .analyze import subject as A_subject
from .analyze import motion as A_motion
from .analyze import scenes as A_scenes
from .analyze import text as A_text
from .analyze.audio import analyze_audio
from .analyze.frames import open_source
from .paths import repo_root
from .util import clamp, die, ok, read_json, step, warn, write_json


def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _round(v, n=3):
    return round(float(v), n) if isinstance(v, (int, float)) else v


def build_style(reference: Path, measurements: dict, base: dict) -> dict:
    """Messwerte in style.json-Felder uebersetzen."""
    style = copy.deepcopy(base)
    cuts = measurements.get("cuts", {})
    motion = measurements.get("motion", {})
    text = measurements.get("text", {})
    col = measurements.get("color", {})
    aud = measurements.get("audio", {})
    face = measurements.get("subject", {})
    dur = measurements.get("duration", 0.0)

    style["meta"] = {
        "name": reference.stem,
        "source": "gemessen mit 'vidkit learn'",
        "measured_from": reference.name,
        "measured_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "notes": "Nur Messwerte — es wurden keine Assets aus dem Referenzvideo uebernommen.",
    }

    # --- Schnittrhythmus -----------------------------------------------------
    if cuts.get("count"):
        style["cuts"].update({
            "avg_shot_seconds": _round(cuts["avg"]),
            "min_shot_seconds": _round(max(0.3, cuts["p10"])),
            "p10_shot_seconds": _round(cuts["p10"]),
            "cuts_per_10s": _round(cuts["cuts_per_10s"], 2),
            "shot_length_histogram": cuts["histogram"]["counts"],
        })
        # Kurze Einstellungen heissen: aggressiver auf Pausen schneiden.
        style["cuts"]["silence_cut"]["min_pause_seconds"] = _round(
            clamp(cuts["median"] * 0.18, 0.20, 0.80), 2)

    # --- Kamerabewegung ------------------------------------------------------
    if motion.get("available"):
        z = style["motion"]["zoom"]
        has_zoom = motion["count"] > 0
        z["enabled"] = bool(has_zoom)
        if has_zoom:
            z["min_scale"] = _round(clamp(motion["zoom_scale_mean"], 1.005, 1.5), 4)
            z["max_scale"] = _round(clamp(motion["zoom_scale_max"], 1.01, 1.6), 4)
            z["duration"] = _round(clamp(motion["zoom_duration_mean"], 0.15, 3.0), 2)
            z["easing"] = motion["easing"]
            z["direction"] = "in" if motion["direction_in_ratio"] >= 0.5 else "out"
            z["max_per_10s"] = _round(motion["moves_per_10s"], 2)
        p = style["motion"]["pan"]
        p["enabled"] = bool(motion.get("pan_share", 0) > 0.15)
        p["max_shift_rel"] = _round(motion.get("pan_max_rel", 0.0), 4)

    # --- Text: grosse Einblendungen und Captions -----------------------------
    for key, section in (("overlays", "overlays"), ("captions", "captions")):
        m = text.get(key) if text.get("available") else None
        if not m:
            continue
        s = style[section]
        s["enabled"] = True
        s["font_size_rel"] = _round(m["font_size_rel"], 4)
        s["position"]["y_rel"] = _round(m["y_rel"], 3)
        s["position"]["x_rel"] = _round(m["x_rel"], 3)
        s["position"]["max_width_rel"] = _round(clamp(m["max_width_rel"] * 1.05, 0.3, 0.95), 3)
        s["uppercase"] = m["uppercase_ratio"] >= 0.5
        if m.get("color"):
            s["color"] = m["color"]
        s["stroke"]["enabled"] = m["outline_ratio"] >= 0.5
        if m.get("outline_color"):
            s["stroke"]["color"] = m["outline_color"]
        if section == "overlays":
            s["per_10s"] = _round(m["per_10s"], 2)
            s["hold_seconds"] = _round(m["hold_seconds"], 2)
            s["words_per_overlay"] = max(1, int(round(m["words_mean"])))
        else:
            s["words_per_group"] = max(1, int(round(m["words_mean"])))
            s["max_group_seconds"] = _round(clamp(m["hold_seconds"], 0.4, 3.0), 2)

    # --- Farblook ------------------------------------------------------------
    if col.get("available"):
        style["color"]["grade"] = col["grade"]
        style["color"]["measured"] = col["measured"]

    # --- Ton -----------------------------------------------------------------
    if aud.get("available"):
        sfx = style["audio"]["sfx"]
        if aud.get("sfx_gain_db_rel_voice") is not None:
            sfx["gain_db_rel_voice"] = _round(clamp(aud["sfx_gain_db_rel_voice"], -30, -2), 1)
        sfx["enabled"] = bool(aud["transients"])
        sfx["on_cut"]["enabled"] = aud["on_cut_rate"] >= 0.2
        sfx["on_cut"]["probability"] = _round(aud["on_cut_rate"], 2)
        sfx["on_overlay"]["enabled"] = aud["on_text_rate"] >= 0.2
        sfx["on_overlay"]["probability"] = _round(aud["on_text_rate"], 2)
        # Tieflastige Transienten sprechen fuer Sub/Impact an Zooms
        low = aud.get("sfx_low_ratio_mean") or 0.0
        sfx["on_zoom"]["enabled"] = bool(low > 0.45 and aud["transients_per_10s"] > 2)
        mus = style["audio"]["music"]
        mus["present"] = bool(aud["music_present"])
        if aud.get("music_gain_db_rel_voice") is not None:
            mus["gain_db_rel_voice"] = _round(clamp(aud["music_gain_db_rel_voice"], -40, -3), 1)

    # --- Dichte --------------------------------------------------------------
    broll_ratio = face.get("broll_ratio") if face.get("available") else None
    if broll_ratio is not None:
        style["broll"]["ratio"] = _round(clamp(broll_ratio, 0.0, 0.8), 3)
        style["broll"]["enabled"] = broll_ratio > 0.05
    style["density"] = {
        "overlays_per_10s": style["overlays"].get("per_10s", 0.0),
        "cuts_per_10s": style["cuts"].get("cuts_per_10s", 0.0),
        "captions_per_10s": _round((text.get("captions") or {}).get("per_10s", 0.0), 2),
        "broll_ratio": style["broll"].get("ratio", 0.0),
        "transients_per_10s": _round(aud.get("transients_per_10s", 0.0), 2)
        if aud.get("available") else 0.0,
        "reference_duration": _round(dur, 2),
    }
    return style


def _report(reference: Path, m: dict, style: dict, out: Path) -> None:
    cuts, motion = m.get("cuts", {}), m.get("motion", {})
    text, col, aud = m.get("text", {}), m.get("color", {}), m.get("audio", {})
    face = m.get("subject", {})
    W = 66
    print("\n" + "═" * W)
    print(f" Gemessen: {reference.name}   {m.get('duration', 0):.1f}s  "
          f"{m.get('width')}x{m.get('height')}")
    print("═" * W)

    print("\n SCHNITTRHYTHMUS")
    if cuts.get("count"):
        print(f"   Einstellungen      {cuts['count']}  ·  {cuts['cuts_per_10s']} Schnitte/10s")
        print(f"   Laenge             ⌀ {cuts['avg']:.2f}s · Median {cuts['median']:.2f}s · "
              f"kuerzeste {cuts['min']:.2f}s · p10 {cuts['p10']:.2f}s")
        edges = ["<0.5", "0.5-1", "1-1.5", "1.5-2", "2-3", "3-4", "4-6", ">6"]
        counts = cuts["histogram"]["counts"]
        mx = max(counts) or 1
        for label, c in zip(edges, counts):
            print(f"     {label:>6}s  {'█' * int(round(14 * c / mx)):<14} {c}")
    else:
        print("   keine Szenenwechsel erkannt")

    print("\n KAMERABEWEGUNG")
    if motion.get("available") and motion.get("count"):
        print(f"   Fahrten            {motion['count']}  ·  {motion['moves_per_10s']}/10s  ·  "
              f"{motion['direction_in_ratio']:.0%} hinein")
        print(f"   Staerke            ⌀ {motion['zoom_scale_mean']:.3f}x · "
              f"max {motion['zoom_scale_max']:.3f}x")
        print(f"   Dauer / Verlauf    {motion['zoom_duration_mean']:.2f}s · {motion['easing']}")
        print(f"   Schwenk-Anteil     {motion['pan_share']:.0%}")
    elif motion.get("available"):
        print("   keine nennenswerte Kamerabewegung")
    else:
        print("   nicht gemessen (OpenCV fehlt)")

    print("\n TEXT IM BILD")
    if text.get("available") and text.get("events"):
        for label, key in (("Grosse Overlays", "overlays"), ("Captions", "captions")):
            t = text.get(key)
            if not t:
                print(f"   {label:<18} keine erkannt")
                continue
            print(f"   {label}")
            print(f"     Dichte           {t['per_10s']}/10s ({t['count']} Stueck)")
            print(f"     Schriftgroesse   {t['font_size_rel']:.3f} der Bildhoehe")
            print(f"     Position         x {t['x_rel']:.2f} · y {t['y_rel']:.2f} · "
                  f"Breite bis {t['max_width_rel']:.2f}")
            print(f"     Standzeit        {t['hold_seconds']:.2f}s · "
                  f"{t['words_mean']:.1f} Woerter")
            print(f"     Schreibweise     {'VERSAL' if t['uppercase_ratio'] >= 0.5 else 'gemischt'}"
                  f" ({t['uppercase_ratio']:.0%})")
            print(f"     Farbe / Kontur   {t['color']} / {t['outline_color']} "
                  f"({'mit' if t['outline_ratio'] >= 0.5 else 'ohne'} Kontur)")
            if t.get("examples"):
                print(f"     Beispiele        {', '.join(repr(x) for x in t['examples'][:3])}")
    elif text.get("available"):
        print("   kein Text erkannt")
    else:
        print("   nicht gemessen (kein OCR installiert)")

    print("\n FARBLOOK")
    if col.get("available"):
        c = col["measured"]
        g = col["grade"]
        print(f"   Helligkeit         {c['luma_mean']:.3f} (p05 {c['luma_p05']:.2f} / "
              f"p95 {c['luma_p95']:.2f})")
        print(f"   Kontrast           {c['contrast_std']:.3f}   Saettigung {c['saturation_mean']:.3f}")
        print(f"   Farbtemperatur     {c['warmth']:+.3f} ({'waermer' if c['warmth'] > 0 else 'kuehler'})")
        print(f"   → Grade            contrast {g['contrast']} · saturation {g['saturation']} · "
              f"brightness {g['brightness']:+} · temp {g['temperature_shift']:+}")
    else:
        print("   nicht gemessen")

    print("\n TON")
    if aud.get("available"):
        print(f"   Sprachanteil       {aud['speech_ratio']:.0%}  ·  Stimme Spitze "
              f"{aud['speech_peak_db']:.1f} dBFS")
        print(f"   Transienten        {len(aud['transients'])} ohne Sprache "
              f"({aud['transients_per_10s']}/10s)")
        print(f"   an Schnitten       {aud['on_cut_rate']:.0%} "
              f"({aud['on_cut_hits']} Treffer)")
        print(f"   an Einblendungen   {aud['on_text_rate']:.0%} "
              f"({aud['on_text_hits']} Treffer)")
        if aud.get("sfx_gain_db_rel_voice") is not None:
            print(f"   Effektpegel        {aud['sfx_gain_db_rel_voice']:+.1f} dB zur Stimme")
        print(f"   Hintergrundmusik   {'ja' if aud['music_present'] else 'nein'}"
              + (f", {aud['music_gain_db_rel_voice']:+.1f} dB zur Stimme"
                 if aud.get("music_gain_db_rel_voice") is not None else ""))
    else:
        print("   nicht gemessen")

    print("\n DICHTE")
    d = style["density"]
    print(f"   Overlays/10s       {d['overlays_per_10s']}")
    print(f"   Schnitte/10s       {d['cuts_per_10s']}")
    print(f"   Captions/10s       {d['captions_per_10s']}")
    if face.get("available"):
        detail = (f"Gesicht in {face['with_face']}/{face['frames']} Frames"
                  if "with_face" in face else
                  f"{face.get('main_group', '?')}/{face.get('shots', '?')} Einstellungen "
                  f"in der Hauptgruppe")
        print(f"   B-Roll-Anteil      {d['broll_ratio']:.0%}  ({face['method']}: {detail})")
    else:
        print(f"   B-Roll-Anteil      {d['broll_ratio']:.0%} (nicht gemessen)")

    print("\n" + "─" * W)
    print(f" geschrieben nach {out}")
    print(" Es wurden nur Werte uebernommen — keine Sounds, keine Grafiken.")
    print("─" * W + "\n")


def learn(reference: Path, *, out: Path, fps_sample: float = 2.0, ocr: bool = True,
          merge: bool = False) -> Path:
    reference = Path(reference)
    if not reference.exists():
        die(f"Referenzvideo nicht gefunden: {reference}")
    src = open_source(reference)
    if src.width == 0:
        die(f"Keine Videospur in {reference}")
    step(f"Analysiere {reference.name}: {src.width}x{src.height}, {src.duration:.1f}s")

    step("  1/6 Szenenwechsel")
    cuts = A_scenes.measure_cuts(reference, src.duration)
    step("  2/6 Kamerabewegung (Optical Flow)")
    motion = A_motion.measure_motion(src, cut_times=cuts.get("cut_times", []))
    step("  3/6 Text im Bild (OCR)" if ocr else "  3/6 Text im Bild — uebersprungen")
    text = A_text.measure_text(src, fps=fps_sample) if ocr else {"available": False}
    step("  4/6 Farblook")
    col = A_color.measure_color(src)
    step("  5/6 Talking Head / B-Roll-Anteil")
    face = A_subject.measure_subject(src, scenes=A_scenes.detect_scenes(reference))
    step("  6/6 Tonspur")
    text_times = []
    for key in ("overlays", "captions"):
        t = (text.get(key) or {}) if text.get("available") else {}
        text_times.extend(t.get("times", []))
    aud = analyze_audio(reference, cut_times=cuts.get("cut_times", []), text_times=text_times)

    measurements = {
        "reference": str(reference), "duration": src.duration,
        "width": src.width, "height": src.height,
        "cuts": cuts, "motion": motion, "text": text, "color": col,
        "subject": face, "audio": aud,
    }

    base_path = repo_root() / "style.json"
    base = read_json(base_path) if base_path.exists() else {}
    style = build_style(reference, measurements, base)
    out = Path(out)
    if merge and out.exists():
        style = _deep_merge(read_json(out), style)

    # Rohmessung daneben legen — nachvollziehbar, aber nicht im Stil-Dokument.
    raw_path = out.with_name(out.stem + ".measurements.json")
    slim = copy.deepcopy(measurements)
    slim["audio"] = {k: v for k, v in aud.items() if k != "transients"}
    slim["audio"]["transient_count"] = len(aud.get("transients", []))
    slim["cuts"] = {k: v for k, v in cuts.items() if k != "shot_lengths"}
    slim["cuts"]["shot_lengths"] = cuts.get("shot_lengths", [])[:200]
    write_json(raw_path, slim)
    write_json(out, style)

    _report(reference, measurements, style, out)
    ok(f"style.json geschrieben · Rohwerte in {raw_path.name}")
    return out
