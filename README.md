# vidkit

Lokale Pipeline, die aus einem Roh-Talking-Head-Video ein geschnittenes
Short-Form-Ad macht. Deutsch, 9:16, fertiges MP4. Alles läuft auf deinem Mac —
kein Cloud-Rendering, keine laufenden Kosten. Der einzige Netzdienst ist Pexels,
und der ist optional.

```
learn (optional) → ingest → transcribe → plan → [ serve ] → assets → sfx → [ stock ] → render
```

Jeder Schritt ist ein eigener Befehl und schreibt sein Ergebnis in eine Datei.
Du kannst jeden Schritt einzeln wiederholen, ohne alles neu zu rendern.

---

## Setup

```bash
brew install ffmpeg tesseract tesseract-lang     # tesseract nur für 'learn'
brew install espeak-ng                           # nur für das Testmaterial
git clone <dieses-repo> && cd Video-editing
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium                      # für die HTML-Overlays
python -m vidkit doctor                          # prüft, was da ist und was fehlt
```

`doctor` sagt dir für jedes fehlende Stück den passenden Installationsbefehl.

**Whisper auf Apple Silicon.** `mlx-whisper` nutzt die GPU über Metal und ist der
schnellste Weg. Ohne Apple Silicon greift automatisch `faster-whisper` (CPU).
Das Modell wird beim ersten Lauf heruntergeladen.

**Sound-Effekte.** Lege deine eigene Bibliothek unter `assets/sfx/` an, nach
Kategorien sortiert:

```
assets/sfx/whoosh/  impact/  pop/  riser/  sub/  click/  transition/
```

Die Ordner sind da, die Sounds bringst du mit. Zum Ausprobieren erzeugt
`python tools/make_placeholder_sfx.py` einen synthetischen Platzhalter-Satz —
mit ffmpeg gerechnet, nicht heruntergeladen. Ersetze ihn durch deinen eigenen.

---

## Der schnelle Weg

```bash
# Stil einmal von einem Referenz-Ad abnehmen
python -m vidkit learn referenz_ad.mp4

# Komplette Kette auf dein Rohvideo
python -m vidkit all rohvideo.mp4 -p kampagne_maerz
```

Ergebnis: `projects/kampagne_maerz/out.mp4`

## Der übliche Weg

```bash
P=kampagne_maerz
python -m vidkit ingest rohvideo.mp4 -p $P     # 1080x1920, 30 fps, -14 LUFS
python -m vidkit transcribe -p $P              # Wort-Timecodes, Deutsch
python -m vidkit plan -p $P                    # → edit.json, der Schnittplan
python -m vidkit serve -p $P --open            # Schnittplan im Browser anpassen
python -m vidkit assets -p $P                  # Overlays als HTML/CSS rendern
python -m vidkit sfx -p $P                     # Sounds auf die Marker legen
python -m vidkit stock -p $P                   # optional: B-Roll-Kandidaten
python -m vidkit render -p $P                  # → out.mp4
```

Zwischen `plan` und `render` gehört die `edit.json` dir. Ändere sie im Editor
oder in `serve` — `render` nimmt, was drinsteht.

---

## Befehle

| Befehl | macht | schreibt |
|---|---|---|
| `learn <referenz.mp4>` | misst den Stil eines fremden Ads aus | `style.json` |
| `ingest <roh.mp4>` | Format, fps, Lautheit normalisieren | `ingest.mp4` |
| `transcribe` | Transkript mit Wort-Timecodes | `transcript.json` |
| `plan` | Schnittplan aus Transkript + Stil | `edit.json` |
| `assets` | Captions/Overlays/Motion als Alpha-Videos | `assets/*.mov` |
| `sfx` | Sounds aus deiner Bibliothek zuordnen | `edit.json` |
| `stock` | B-Roll-Kandidaten von Pexels laden | `stock/`, `edit.json` |
| `render` | alles zusammensetzen | `out.mp4` |
| `preview` | dasselbe in halber Auflösung | `preview.mp4` |
| `serve` | Weboberfläche zum Bearbeiten | — |
| `all` | die ganze Kette | `out.mp4` |
| `doctor` | prüft die Installation | — |

Für alle Befehle: `-p/--project` wählt den Projektordner, `--style` eine andere
`style.json`, `-v` zeigt die ffmpeg-Kommandos, `--no-hw` schaltet das
Hardware-Encoding ab.

### `learn` — Stil ausmessen

```bash
python -m vidkit learn referenz_ad.mp4              # schreibt style.json
python -m vidkit learn referenz_ad.mp4 -o stile/schnell.json
python -m vidkit learn referenz_ad.mp4 --merge      # nur gemessene Felder ersetzen
python -m vidkit learn referenz_ad.mp4 --no-ocr     # ohne Textanalyse, schneller
```

Gemessen wird:

* **Schnittrhythmus** — PySceneDetect: Anzahl, mittlere/kürzeste Einstellung, Verteilung als Histogramm
* **Kamerabewegung** — Optical Flow (Farneback), zerlegt in Zoom und Schwenk: Stärke, Dauer, Verlauf (welche Easing-Kurve passt)
* **Text im Bild** — OCR, getrennt nach großen Einblendungen und Captions: Position, Schriftgröße relativ zur Bildhöhe, Farbe, Kontur, Groß-/Kleinschreibung, Wörter pro Einblendung, Standzeit
* **Farblook** — Histogramm, Sättigung, Kontrast, Farbtemperatur, umgerechnet in annähernde Grade-Werte
* **Ton** — Sprache gegen Nicht-Sprache getrennt, Transienten gesucht: sitzen Effekte auf Schnitten? auf Einblendungen? wie laut zur Stimme? läuft Musik?
* **Dichte** — Overlays, Schnitte und Captions pro 10 Sekunden, B-Roll-Anteil

Im Terminal steht danach ein Report mit allen Messwerten zum Nachprüfen. Die
Rohwerte landen zusätzlich in `style.measurements.json`.

**Es werden nur Zahlen übernommen.** Kein Bild, kein Ton, keine Grafik aus dem
Referenzvideo wandert in dein Projekt.

### `serve` — Schnittplan im Browser

```bash
python -m vidkit serve -p kampagne_maerz --open
```

Läuft auf `127.0.0.1:8777`, ohne Anmeldung, ohne Internet. Links das Video,
darunter die Zeitleiste mit allen Elementen aus der `edit.json` als Blöcke:
Captions, Overlays, Zooms, Motion Graphics, B-Roll, Sounds.

* Block ziehen = verschieben, an den Rändern ziehen = verlängern
* Block anklicken = Text, Zeiten und Einstellungen rechts bearbeiten
* Entf löscht, Leertaste startet und stoppt, ⌘S speichert
* Änderungen gehen direkt in die `edit.json` (automatisch nach kurzer Pause)
* „Rendern" startet den Render-Schritt und zeigt das Log

Angezeigt wird die zuletzt gerenderte Fassung (`preview.mp4`, sonst `out.mp4`).
Ist noch nichts gerendert, siehst du `ingest.mp4` — dessen Zeiten weichen von
der geschnittenen Fassung ab, die Oberfläche sagt das an.

### `stock` — B-Roll

```bash
export PEXELS_API_KEY=…            # kostenlos auf pexels.com/api
python -m vidkit stock -p kampagne_maerz --per-slot 5
```

Lädt pro B-Roll-Slot fünf Kandidaten nach `projects/<p>/stock/<slot>/` und
trägt sie in die `edit.json` ein. **Ausgewählt wird nicht automatisch.** Setz
`selection` auf eine Kandidaten-ID (von Hand oder in `serve`), dann nimmt
`render` diesen Clip.

---

## `style.json` — der ganze Stil an einer Stelle

Im Code steht kein einziger Stilwert. Willst du etwas ändern, änderst du eine
Zahl in der `style.json` und renderst neu.

```jsonc
{
  "format":   { "width": 1080, "height": 1920, "fps": 30 },
  "safe_zones": { "top": 0.08, "bottom": 0.20, "left": 0.06, "right": 0.14 },
  "cuts": {
    "silence_cut": { "enabled": true, "min_pause_seconds": 0.45 },
    "cut_filler_words": true,
    "filler_words": ["ähm", "äh", "öhm"]
  },
  "motion": { "zoom": { "max_scale": 1.08, "duration": 0.45,
                        "easing": "easeOutCubic", "max_per_10s": 2.5 } },
  "captions": {
    "words_per_group": 3, "font_size_rel": 0.042,
    "position": { "x_rel": 0.5, "y_rel": 0.70 },
    "color": "#FFFFFF", "active_color": "#D6FF3D",
    "stroke": { "enabled": true, "width_rel": 0.0055, "color": "#000000" },
    "animation": { "in": "pop", "in_duration": 0.12, "overshoot": 1.08 }
  },
  "overlays": { "per_10s": 1.4, "font_size_rel": 0.085, "hold_seconds": 0.7,
                "animation": { "in": "slide_up", "distance_rel": 0.05,
                               "overshoot": 1.05, "easing": "easeOutBack" } },
  "audio": {
    "voice_lufs": -14.0,
    "sfx": { "gain_db_rel_voice": -12.0,
             "on_cut":     { "enabled": true, "probability": 0.8,
                             "categories": ["whoosh", "transition"] },
             "on_overlay": { "enabled": true, "probability": 0.9,
                             "categories": ["pop", "impact", "click"] } }
  }
}
```

Ein paar Regeln, die überall gelten:

* Alle Größen mit `_rel` sind relativ zur **Bildhöhe** — der Stil überträgt sich
  damit auf jedes Format.
* `per_10s` steuert Dichte, nicht Anzahl: bei einem 30-Sekunden-Video ergibt
  `1.4` vier Overlays.
* **Safe Zones** halten unten und rechts Platz für die Plattform-Oberfläche
  (TikTok, Reels, Shorts). Nichts wird beschnitten — Elemente rücken hinein.
* Verfügbare Easings: `linear`, `easeOutQuad`, `easeOutCubic`, `easeInOutCubic`,
  `easeInOutSine`, `easeOutBack`, `easeOutExpo`.

### Anderes Format

`format` auf `1080x1080` oder `1920x1080` setzen, Safe Zones anpassen — der Rest
rechnet sich mit, weil alle Größen relativ sind.

### Eigene Schrift

```jsonc
"typography": {
  "font_family": "\"Meine Schrift\", Helvetica, Arial, sans-serif",
  "font_files": [
    { "file": "assets/fonts/MeineSchrift-Black.woff2",
      "family": "Meine Schrift", "weight": 900 }
  ],
  "font_weight": 900
}
```

Die Datei wird beim Rendern als data-URI in die Seite eingebettet — Chromium
lädt nichts nach.

---

## `edit.json` — der Schnittplan

Das Ergebnis von `plan` und die einzige Datei, die `render` liest.

```jsonc
{
  "segments": [ { "id": "seg000", "source_in": 0.62, "source_out": 2.40,
                  "t_in": 0.0, "t_out": 1.78 } ],
  "captions": [ { "id": "cap000", "t_in": 0.08, "t_out": 1.24,
                  "text": "Hallo ich bin",
                  "words": [ { "w": "Hallo", "t_in": 0.0, "t_out": 0.40 } ] } ],
  "overlays": [ { "id": "ovl000", "t_in": 9.13, "t_out": 10.26,
                  "text": "Kein Aufwand" } ],
  "zooms":    [ { "id": "zom000", "t_in": 5.57, "t_out": 6.02,
                  "from": 1.0, "to": 1.075, "easing": "easeOutCubic" } ],
  "broll":    [ { "id": "brl000", "t_in": 5.42, "t_out": 7.92,
                  "queries": ["produkt", "morgen"], "selection": null } ],
  "sfx":      [ { "id": "sfx000", "t": 1.75, "reason": "cut",
                  "category": "whoosh", "file": "assets/sfx/whoosh/a.wav",
                  "gain_db": -5.2 } ]
}
```

* `segments` sind die **behaltenen** Stücke. `source_in/out` zeigen ins
  `ingest.mp4`, `t_in/out` in die fertige Fassung. Die Lücken dazwischen sind die
  Schnitte.
* Alle anderen Zeiten liegen in der **fertigen** Zeitachse.
* `enabled: false` schaltet ein Element ab, ohne es zu löschen.
* Wortzeiten in Captions sind relativ zum Blockanfang.

---

## Ordnerstruktur

```
style.json                      dein Stil
assets/sfx/<kategorie>/         deine Sound-Bibliothek
assets/fonts/                   deine Schriften (optional)
projects/<name>/
  ingest.mp4                    normalisiert
  transcript.json               Wort-Timecodes
  edit.json                     der Schnittplan  ← den fasst du an
  style.json                    optional: Stil nur für dieses Projekt
  assets/                       Overlays als Alpha-MOV + _html/ zum Nachsehen
  stock/<slot>/                 B-Roll-Kandidaten
  render/base|composite|mix     Zwischenstufen
  out.mp4                       das Ergebnis
```

Liegt in einem Projektordner eine eigene `style.json`, hat sie Vorrang vor der
globalen.

---

## Wiederholen ohne alles neu zu rechnen

`render` läuft in vier Stufen, jede schreibt eine Datei:

| Stufe | macht | Datei |
|---|---|---|
| `base` | Schnitte, Zooms, Farblook | `render/base.mp4` |
| `composite` | B-Roll, Overlays, Captions | `render/composite.mp4` |
| `audio` | Stimme, Sounds, Musik | `render/mix.wav` |
| `mux` | Bild und Ton zusammen | `out.mp4` |

```bash
python -m vidkit render -p $P --from-stage composite   # nur Overlays neu
python -m vidkit render -p $P --from-stage audio       # nur Ton neu
```

`assets` merkt sich einen Hash je Element und rendert nur, was sich geändert
hat. `--force` erzwingt alles, `--only cap003,ovl001` nur einzelne.

---

## Geschwindigkeit

Auf Apple Silicon läuft das Encoding über VideoToolbox (`h264_videotoolbox`),
sonst über `libx264` — automatisch, `doctor` zeigt an, welcher greift.
`--no-hw` erzwingt die Software.

Der langsamste Schritt ist `assets`: jedes Frame wird einzeln aus Chromium
geholt. Es werden nur die tatsächlich sichtbaren Frames gerendert und nur der
Ausschnitt, in dem das Element liegt. Ein Element ändern und neu rendern kostet
Sekunden, nicht Minuten.

---

## Testlauf

Das Testmaterial wird lokal erzeugt, nichts wird heruntergeladen. Die Sprachspur
synthetisiert `espeak-ng` (`brew install espeak-ng`):

```bash
python tests/make_fixture.py       # Rohvideo + Transkript mit exakten Zeiten
python tests/make_reference.py     # Referenz-Ad mit bekannten Sollwerten
python tools/make_placeholder_sfx.py

python -m vidkit ingest tests/fixtures/sample_talking_head.mp4 -p demo
python -m vidkit transcribe -p demo --import tests/fixtures/sample_transcript.json
python -m vidkit plan -p demo --force
python -m vidkit assets -p demo
python -m vidkit sfx -p demo
python -m vidkit render -p demo

python tests/check_learn.py        # prüft 'learn' gegen die Sollwerte
python tests/test_stock_offline.py # prüft 'stock' ohne Netz
```

`--import` übernimmt ein fertiges Transkript, statt Whisper laufen zu lassen —
praktisch für Tests und wenn du das Transkript von woanders hast.

---

## Wenn etwas klemmt

**`ffmpeg nicht gefunden`** → `brew install ffmpeg`

**`Kein Whisper-Backend gefunden`** → `pip install mlx-whisper` (Apple Silicon)
oder `pip install faster-whisper`

**`playwright fehlt`** → `pip install playwright && playwright install chromium`.
Hast du Chromium schon woanders liegen: `export VIDKIT_CHROMIUM_PATH=/pfad/zu/chrome`

**`learn` misst keinen Text** → tesseract fehlt: `brew install tesseract
tesseract-lang`. `easyocr` liefert genauere Kästen, ist aber deutlich größer.

**`learn` misst zu wenig Zoom** → Optical Flow braucht Struktur im Bild. Bei
sehr flächigem Material (weiße Wand, starke Unschärfe) fällt die Messung
niedriger aus. Der Wert steht in `style.json` unter `motion.zoom.max_scale` und
lässt sich von Hand korrigieren.

**Sounds sind zu laut oder zu leise** → `audio.sfx.gain_db_rel_voice`. Der Pegel
wird gegen die Spitze deiner Stimme gerechnet, nicht gegen die Rohdatei.

**Ein Overlay sitzt falsch** → `overlays.position.y_rel` in der `style.json`
(gilt für alle) oder den Block in `serve` verschieben (gilt für diesen einen).

---

## Was dieses Werkzeug nicht tut

* Kein Cloud-Rendering, keine Abo-Dienste
* Keine CapCut-Integration
* Keine Assets aus fremden Videos — `learn` misst Werte, sonst nichts
