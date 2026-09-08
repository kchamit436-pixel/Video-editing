#!/usr/bin/env python3
"""Erzeugt .cube-LUTs aus den Beschreibungen in assets/luts/looks.json.

Eine LUT ist eine Nachschlagetabelle: fuer Stuetzstellen im RGB-Wuerfel steht
darin, welche Farbe herauskommen soll. Jedes Schnittprogramm, das .cube liest
(CapCut, Resolve, Premiere, ffmpeg), wendet sie damit auf jedes Bild an.

  python3 tools/make_lut.py --alle
  python3 tools/make_lut.py --look warm_marke --groesse 33
  python3 tools/make_lut.py --vorschau bild.jpg     # Vorher/Nachher als PNG

Kein Stilwert steht hier im Code, alle Zahlen kommen aus der looks.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

WURZEL = Path(__file__).resolve().parent.parent
LOOKS_DATEI = WURZEL / "assets" / "luts" / "looks.json"
ZIELORDNER = WURZEL / "assets" / "luts"

# Rec.709 — dieselben Gewichte, mit denen jedes Schnittprogramm Helligkeit misst.
LUMA = np.array([0.2126, 0.7152, 0.0722])

# Hautton liegt im Farbkreis bei ungefaehr 25 Grad (orange). Der Wert ist der
# Mittelpunkt des geschuetzten Bereichs, die Breite sein Auslaufen.
HAUT_WINKEL = 25.0
HAUT_BREITE = 26.0


def srgb_nach_linear(x: np.ndarray) -> np.ndarray:
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_nach_srgb(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, None)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


def _luma(rgb: np.ndarray) -> np.ndarray:
    return rgb @ LUMA


def _hautgewicht(rgb: np.ndarray) -> np.ndarray:
    """Wie sehr eine Farbe nach Haut aussieht, 0 bis 1.

    Ueber den Farbwinkel, nicht ueber die Helligkeit: dunkle und helle Haut
    liegen im selben Winkelbereich, unterscheiden sich aber in der Helligkeit.
    Graue und sehr blasse Farben werden ausgenommen, sonst wuerde der Schutz
    auch auf Waende und Kleidung greifen.
    """
    maxi = rgb.max(axis=-1)
    mini = rgb.min(axis=-1)
    spanne = maxi - mini
    # Bei Grau gibt es keinen Winkel; die Division wird abgefangen.
    sicher = np.where(spanne < 1e-6, 1.0, spanne)

    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    winkel = np.where(
        maxi == r,
        ((g - b) / sicher) % 6,
        np.where(maxi == g, (b - r) / sicher + 2, (r - g) / sicher + 4),
    ) * 60.0

    abstand = np.abs((winkel - HAUT_WINKEL + 180) % 360 - 180)
    naehe = np.exp(-((abstand / HAUT_BREITE) ** 2))

    # Farblose Stellen sind keine Haut.
    saettigung = np.where(maxi < 1e-6, 0.0, spanne / np.where(maxi < 1e-6, 1.0, maxi))
    return naehe * np.clip(saettigung / 0.18, 0.0, 1.0)


def _scurve(x: np.ndarray, pivot: float) -> np.ndarray:
    """Weiche S-Kurve, die 0 und 1 stehen laesst und um den Pivot dreht.

    Der Pivot sitzt bewusst unter 0.5: bei 0.5 hebt jede Kontrastkurve das
    Gesicht mit an, und aufgehellte Haut sieht sofort nach Handyfilter aus.
    """
    unten = x < pivot
    oben = ~unten
    y = np.empty_like(x)
    # Zwei Halbparabeln, an der Nahtstelle steigungsgleich.
    y[unten] = pivot * (x[unten] / pivot) ** 2
    y[oben] = 1 - (1 - pivot) * ((1 - x[oben]) / (1 - pivot)) ** 2
    return y


def grade(rgb: np.ndarray, p: dict) -> np.ndarray:
    """Wendet einen Look auf Werte in 0..1 an. Reihenfolge ist Absicht."""
    x = np.clip(rgb.astype(np.float64), 0.0, 1.0)

    # 1. Belichtung und Weissabgleich im linearen Licht. In Gammawerten
    #    gerechnet kippen beide die Farben, statt sie nur zu verschieben.
    lin = srgb_nach_linear(x)
    lin *= 2.0 ** p["belichtung"]

    temp = p["temperatur"]
    tint = p["tint"]
    faktoren = np.array(
        [1.0 + 0.18 * temp, 1.0 - 0.09 * tint, 1.0 - 0.18 * temp], dtype=np.float64
    )
    # Auf gleiche Helligkeit normieren, damit der Weissabgleich nicht nebenbei
    # abdunkelt.
    lin = lin * faktoren / float(faktoren @ LUMA)
    x = linear_nach_srgb(lin)

    # 2. Schwarzpunkt anheben. Das nimmt dem Bild die harte Kante nach unten
    #    und ist der halbe Unterschied zwischen "Handyvideo" und "gegradet".
    schwarz = p["schwarzpunkt"]
    x = schwarz + x * (1.0 - schwarz)

    # 3. Kontrast als Anteil der S-Kurve, nicht als harte Kurve.
    staerke = p["kontrast"]
    if staerke > 0:
        x = x + (_scurve(np.clip(x, 0, 1), p["pivot"]) - x) * staerke

    # 4. Teiltonung: Schatten und Lichter in verschiedene Richtungen. Der
    #    Mittelton — und damit das Gesicht — bleibt dabei weitgehend liegen.
    y = _luma(x)[..., None]
    schatten_w = (1.0 - np.clip(y, 0, 1)) ** 2
    lichter_w = np.clip(y, 0, 1) ** 2
    x = x + np.array(p["schatten_farbe"]) * p["schatten_staerke"] * schatten_w
    x = x + np.array(p["lichter_farbe"]) * p["lichter_staerke"] * lichter_w
    x = np.clip(x, 0.0, 1.0)

    # 5. Saettigung. Zwei Bremsen: 'dynamik' laesst ohnehin bunte Stellen in
    #    Ruhe, 'hautschutz' nimmt den Effekt genau dort zurueck, wo Haut ist.
    y = _luma(x)[..., None]
    maxi = x.max(axis=-1, keepdims=True)
    mini = x.min(axis=-1, keepdims=True)
    ist_bunt = np.where(maxi < 1e-6, 0.0, (maxi - mini) / np.maximum(maxi, 1e-6))

    faktor = np.full_like(y, p["saettigung"])
    faktor = 1.0 + (faktor - 1.0) * (1.0 - p["dynamik"] * ist_bunt)
    haut = _hautgewicht(x)[..., None]
    faktor = 1.0 + (faktor - 1.0) * (1.0 - p["hautschutz"] * haut)

    x = y + (x - y) * faktor

    return np.clip(x, 0.0, 1.0)


def schreibe_cube(pfad: Path, name: str, p: dict, groesse: int) -> None:
    """Schreibt die LUT im .cube-Format.

    Wichtig ist die Reihenfolge: Rot laeuft am schnellsten, Blau am
    langsamsten. Andersherum sind die Farbkanaele im Ergebnis vertauscht.
    """
    achse = np.linspace(0.0, 1.0, groesse)
    b, g, r = np.meshgrid(achse, achse, achse, indexing="ij")
    gitter = np.stack([r, g, b], axis=-1).reshape(-1, 3)

    ergebnis = grade(gitter, p)

    zeilen = [
        f'TITLE "{p["titel"]}"',
        f"# {p['beschreibung']}",
        f"# erzeugt von tools/make_lut.py aus assets/luts/looks.json ({name})",
        f"LUT_3D_SIZE {groesse}",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
        "",
    ]
    zeilen += [f"{w[0]:.6f} {w[1]:.6f} {w[2]:.6f}" for w in ergebnis]

    pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")


def lies_cube(pfad: Path) -> tuple[np.ndarray, int]:
    """Liest eine .cube zurueck — zum Pruefen, dass das Geschriebene stimmt."""
    groesse = 0
    werte = []
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or zeile.startswith("TITLE"):
            continue
        if zeile.startswith("LUT_3D_SIZE"):
            groesse = int(zeile.split()[1])
            continue
        if zeile.startswith("DOMAIN"):
            continue
        werte.append([float(t) for t in zeile.split()])
    tabelle = np.array(werte, dtype=np.float64)
    return tabelle.reshape(groesse, groesse, groesse, 3), groesse


def wende_lut_an(bild: np.ndarray, tabelle: np.ndarray) -> np.ndarray:
    """Trilineare Interpolation im Wuerfel — so macht es das Schnittprogramm."""
    n = tabelle.shape[0]
    pos = np.clip(bild, 0, 1) * (n - 1)
    i0 = np.floor(pos).astype(int)
    i1 = np.minimum(i0 + 1, n - 1)
    f = pos - i0

    r0, g0, b0 = i0[..., 0], i0[..., 1], i0[..., 2]
    r1, g1, b1 = i1[..., 0], i1[..., 1], i1[..., 2]
    fr, fg, fb = f[..., 0:1], f[..., 1:2], f[..., 2:3]

    # tabelle ist [blau][gruen][rot], passend zur Schreibreihenfolge.
    def hole(ri, gi, bi):
        return tabelle[bi, gi, ri]

    c00 = hole(r0, g0, b0) * (1 - fr) + hole(r1, g0, b0) * fr
    c01 = hole(r0, g0, b1) * (1 - fr) + hole(r1, g0, b1) * fr
    c10 = hole(r0, g1, b0) * (1 - fr) + hole(r1, g1, b0) * fr
    c11 = hole(r0, g1, b1) * (1 - fr) + hole(r1, g1, b1) * fr

    c0 = c00 * (1 - fg) + c10 * fg
    c1 = c01 * (1 - fg) + c11 * fg
    return c0 * (1 - fb) + c1 * fb


def testbild(breite: int = 480, hoehe: int = 540) -> np.ndarray:
    """Hauttoene, Graukeil und Farbfelder — genug, um einen Look zu beurteilen."""
    bild = np.zeros((hoehe, breite, 3), dtype=np.float64)

    hauttoene = [
        (0.98, 0.83, 0.74),
        (0.90, 0.71, 0.60),
        (0.76, 0.56, 0.45),
        (0.55, 0.38, 0.29),
        (0.36, 0.24, 0.18),
        (0.22, 0.14, 0.10),
    ]
    felder = [
        (0.85, 0.15, 0.15),
        (0.15, 0.55, 0.85),
        (0.20, 0.65, 0.30),
        (0.95, 0.80, 0.20),
        (0.55, 0.55, 0.58),
        (0.10, 0.10, 0.12),
    ]

    zeilenhoehe = hoehe // 3
    spalte = breite // 6
    for i, farbe in enumerate(hauttoene):
        bild[0:zeilenhoehe, i * spalte : (i + 1) * spalte] = farbe
    for i, farbe in enumerate(felder):
        bild[zeilenhoehe : 2 * zeilenhoehe, i * spalte : (i + 1) * spalte] = farbe

    keil = np.linspace(0.0, 1.0, breite)[None, :, None]
    bild[2 * zeilenhoehe :, :] = keil
    return bild


def vorschau(bildpfad: Path | None, namen: list[str], looks: dict, ziel: Path) -> None:
    from PIL import Image

    if bildpfad is None:
        original = testbild()
    else:
        original = np.asarray(Image.open(bildpfad).convert("RGB"), dtype=np.float64) / 255
        # Auf handliche Breite bringen, die Farben aendern sich dadurch nicht.
        if original.shape[1] > 480:
            faktor = 480 / original.shape[1]
            neu = Image.fromarray((original * 255).astype(np.uint8)).resize(
                (480, max(1, int(original.shape[0] * faktor)))
            )
            original = np.asarray(neu, dtype=np.float64) / 255

    streifen = [original]
    for name in namen:
        tabelle, _ = lies_cube(ZIELORDNER / f"{name}.cube")
        streifen.append(wende_lut_an(original, tabelle))

    zusammen = np.concatenate(streifen, axis=1)
    Image.fromarray((np.clip(zusammen, 0, 1) * 255).astype(np.uint8)).save(ziel)
    print(f"Vorschau geschrieben: {ziel}  (links Original, dann {', '.join(namen)})")


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--look", help="Name eines Looks aus der looks.json")
    zerleger.add_argument("--alle", action="store_true", help="alle Looks erzeugen")
    zerleger.add_argument("--groesse", type=int, default=33, help="Stuetzstellen je Kanal")
    zerleger.add_argument("--vorschau", nargs="?", const="", metavar="BILD",
                          help="Vorher/Nachher-PNG; ohne Datei mit Testbild")
    argumente = zerleger.parse_args()

    if not LOOKS_DATEI.exists():
        print(f"Fehlt: {LOOKS_DATEI}", file=sys.stderr)
        return 1
    looks = json.loads(LOOKS_DATEI.read_text(encoding="utf-8"))

    if argumente.look and argumente.look not in looks:
        print(f"Unbekannter Look '{argumente.look}'. Vorhanden: {', '.join(looks)}",
              file=sys.stderr)
        return 1

    namen = [argumente.look] if argumente.look else list(looks)

    if argumente.alle or argumente.look or argumente.vorschau is None:
        ZIELORDNER.mkdir(parents=True, exist_ok=True)
        for name in namen:
            pfad = ZIELORDNER / f"{name}.cube"
            schreibe_cube(pfad, name, looks[name], argumente.groesse)
            kb = pfad.stat().st_size / 1024
            print(f"{pfad.relative_to(WURZEL)}  ({argumente.groesse}^3, {kb:.0f} kB)")

    if argumente.vorschau is not None:
        quelle = Path(argumente.vorschau) if argumente.vorschau else None
        vorschau(quelle, namen, looks, ZIELORDNER / "vorschau.png")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
