"""Tonspur zerlegen: Sprache vs. Nicht-Sprache, Transienten, Musik.

Daraus wird abgeleitet, ob an Schnitten und Text-Einblendungen Sound-Effekte
sitzen, wie laut sie zur Stimme stehen und ob Musik mitlaeuft.
"""
from __future__ import annotations

import numpy as np

from ..ffmpeg import read_audio_mono
from ..util import debug

SR = 16000
HOP = 256          # 16 ms
WIN = 512


def _frames(x: np.ndarray) -> np.ndarray:
    n = 1 + max(0, (len(x) - WIN) // HOP)
    idx = np.arange(WIN)[None, :] + HOP * np.arange(n)[:, None]
    return x[idx] if n else np.zeros((0, WIN), dtype=x.dtype)


def _db(x: float) -> float:
    return float(20 * np.log10(max(x, 1e-9)))


def analyze_audio(path, *, cut_times: list[float] | None = None,
                  text_times: list[float] | None = None) -> dict:
    x, sr = read_audio_mono(path, SR)
    if len(x) < WIN * 4:
        return {"available": False}
    fr = _frames(x)
    win = np.hanning(WIN).astype(np.float32)
    spec = np.abs(np.fft.rfft(fr * win, axis=1)) + 1e-9
    freqs = np.fft.rfftfreq(WIN, 1 / sr)
    times = np.arange(len(fr)) * HOP / sr

    rms = np.sqrt((fr ** 2).mean(axis=1)) + 1e-9
    rms_db = 20 * np.log10(rms)

    # Sprachband gegen Rest: Stimme sitzt in 300-3400 Hz
    band = (freqs >= 300) & (freqs <= 3400)
    low = freqs < 300
    speech_ratio = spec[:, band].sum(axis=1) / spec.sum(axis=1)
    # Spektrale Flachheit: Rauschen/Perkussion flach, Stimme/Musik tonal
    flatness = np.exp(np.log(spec).mean(axis=1)) / spec.mean(axis=1)

    floor = np.percentile(rms_db, 20)
    peak = np.percentile(rms_db, 95)
    gate = floor + 0.35 * (peak - floor)
    is_loud = rms_db > gate
    is_speech = is_loud & (speech_ratio > 0.45) & (flatness < 0.35)

    # kurze Luecken in der Sprache schliessen (Wortpausen sind keine Nicht-Sprache)
    sp = is_speech.copy()
    gap = int(0.20 * sr / HOP)
    i = 0
    while i < len(sp):
        if not sp[i]:
            j = i
            while j < len(sp) and not sp[j]:
                j += 1
            if 0 < i and j < len(sp) and (j - i) <= gap:
                sp[i:j] = True
            i = j
        else:
            i += 1
    is_speech = sp
    non_speech = ~is_speech

    # Transienten ueber spektralen Fluss. Ob ein Anschlag zur Sprache gehoert,
    # entscheidet sein Klang an genau dieser Stelle — nicht die Sprachmaske:
    # ein Effekt, der auf einem Wort sitzt, faellt sonst unter den Tisch.
    flux = np.zeros(len(spec))
    d = np.diff(spec, axis=0)
    flux[1:] = np.maximum(d, 0).sum(axis=1)
    flux = flux / (np.median(flux) + 1e-9)
    # Adaptive Schwelle statt globalem Perzentil: in dichter Sprache liegen die
    # obersten Prozent des Flusses saemtlich auf Wortanfaengen, ein globaler
    # Wert findet dann keinen einzigen Effekt. Gegen bekannte Marker gemessen:
    # global 1/8 Treffer, adaptiv 6/8.
    w = int(0.5 * sr / HOP)
    local = np.array([np.median(flux[max(0, i - w):i + w + 1]) for i in range(len(flux))])
    thr_arr = local * 2.2 + float(np.percentile(flux, 60)) * 0.3
    transients: list[dict] = []
    min_gap = int(0.08 * sr / HOP)
    last = -10 ** 6
    for i in range(1, len(flux) - 1):
        if flux[i] < thr_arr[i] or flux[i] < flux[i - 1] or flux[i] < flux[i + 1]:
            continue
        if (i - last) <= min_gap:
            continue
        # Nicht-Sprache: Energie ausserhalb des Sprachbandes oder rauschartig
        non_voice = (speech_ratio[i] < 0.55) or (flatness[i] > 0.40)
        if not (non_voice or non_speech[i]):
            continue
        transients.append({"t": round(float(times[i]), 3),
                           "strength": round(float(flux[i] / max(local[i], 1e-9)), 2),
                           "peak_db": round(_db(float(np.abs(fr[i]).max())), 1),
                           "speech_ratio": round(float(speech_ratio[i]), 3),
                           "in_speech": bool(is_speech[i]),
                           "low_ratio": round(float(spec[i, low].sum() / spec[i].sum()), 3)})
        last = i

    duration = len(x) / sr
    speech_db = _db(float(np.percentile(np.abs(x), 99.5))) if is_speech.any() else -99.0
    speech_rms_db = float(np.mean(rms_db[is_speech])) if is_speech.any() else -99.0
    ns_rms = rms_db[non_speech]
    ns_rms_db = float(np.median(ns_rms)) if len(ns_rms) else -99.0

    # Musik: laeuft im Nicht-Sprache-Anteil dauerhaft Pegel mit geringer Streuung?
    music_present = False
    music_level_db = None
    if len(ns_rms) > 20:
        above_floor = ns_rms > (floor + 6)
        share = float(above_floor.mean())
        spread = float(np.std(ns_rms[above_floor])) if above_floor.any() else 99.0
        music_present = bool(share > 0.45 and spread < 9.0)
        if music_present:
            music_level_db = round(float(np.median(ns_rms[above_floor])) - speech_rms_db, 1)

    def hit_rate(marks: list[float] | None, tol: float = 0.18) -> tuple[float, int]:
        if not marks:
            return (0.0, 0)
        hits = sum(1 for m in marks if any(abs(tr["t"] - m) <= tol for tr in transients))
        return (round(hits / len(marks), 2), hits)

    cut_rate, cut_hits = hit_rate(cut_times)
    text_rate, text_hits = hit_rate(text_times)

    sfx_peaks = [tr["peak_db"] for tr in transients]
    sfx_rel = round(float(np.median(sfx_peaks)) - speech_db, 1) if sfx_peaks else None

    debug(f"Audio: Sprache {is_speech.mean():.0%}, {len(transients)} Transienten")
    return {
        "available": True,
        "duration": round(duration, 2),
        "speech_ratio": round(float(is_speech.mean()), 3),
        "speech_peak_db": round(speech_db, 1),
        "speech_rms_db": round(speech_rms_db, 1),
        "non_speech_rms_db": round(ns_rms_db, 1),
        "transients": transients,
        "transients_per_10s": round(len(transients) / (duration / 10), 2) if duration else 0.0,
        "sfx_gain_db_rel_voice": sfx_rel,
        "sfx_low_ratio_mean": round(float(np.mean([t["low_ratio"] for t in transients])), 3)
        if transients else None,
        "music_present": music_present,
        "music_gain_db_rel_voice": music_level_db,
        "on_cut_rate": cut_rate, "on_cut_hits": cut_hits,
        "on_text_rate": text_rate, "on_text_hits": text_hits,
    }
