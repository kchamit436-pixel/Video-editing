# CLAUDE.md — Projektregeln

Kurzfassung für künftige Sessions. Was das Werkzeug kann, steht im README;
hier steht, wie daran gearbeitet wird.

## Worum es geht

`vidkit` macht aus einem deutschsprachigen Roh-Talking-Head-Video ein
geschnittenes 9:16-Short-Form-Ad. Der Nutzer ist Solo-Founder und dreht das
regelmäßig für seine DTC-Marke — es ist ein **wiederverwendbares Werkzeug**,
kein Einmal-Skript.

## Grundprinzipien

1. **Config-getrieben.** Kein Stilwert steht im Code. Alles kommt aus
   `style.json`. Fällt dir auf, dass eine Zahl im Code steht, gehört sie in die
   Config — mit Default in `style.json`, gelesen über `Style.get()`.
2. **Schritte einzeln aufrufbar.** Jeder Schritt ist ein eigener Befehl und
   schreibt sein Ergebnis in eine Datei. Kein Schritt darf einen anderen
   erzwingen. Ein Schritt muss wiederholbar sein, ohne alles neu zu rechnen.
3. **Ein Mensch darf dazwischen.** `edit.json` ist ein Vertrag: `plan` schreibt
   sie, ein Mensch ändert sie, `render` liest sie. Keine automatische
   Nachkorrektur im Render — was in der `edit.json` steht, gilt.
4. **Schnell auf Apple Silicon.** VideoToolbox zum Encoden, mlx-whisper zum
   Transkribieren, wo verfügbar. Immer mit Rückfalloption, damit es überall läuft.
5. **Alles lokal.** Der einzige erlaubte Netzdienst ist Pexels in `stock`, und
   der ist optional.

## Harte Grenzen

* **Keine Assets aus fremden Videos.** `learn` misst Zahlen. Es extrahiert
  keine Sounds, keine Grafiken, keine Bildausschnitte. Diese Regel steht nicht
  zur Diskussion.
* **Keine Cloud-Renderdienste, keine Abo-Tools, keine CapCut-Integration.**
* **Kein SFX-Download.** Sounds kommen ausschließlich aus `assets/sfx/`.
  `tools/make_placeholder_sfx.py` *synthetisiert* Platzhalter mit ffmpeg —
  das ist erzeugen, nicht herunterladen.
* **Text nicht mit ffmpeg `drawtext`.** Overlays und Captions laufen über
  HTML/CSS in Chromium. Grund: freie Typografie, echtes Easing, Overshoot.

## Aufbau

```
vidkit/
  cli.py          Befehlszeile, ein Unterbefehl je Schritt
  config.py       style.json laden, mergen, Punktzugriff (Style.get)
  paths.py        Projektpfade; resolve_asset() löst Pfade aus der edit.json
  editdoc.py      edit.json lesen/schreiben/sortieren, Schema-Version
  edits.py        Schnittoperationen: Passage loeschen/teilen/trimmen (Ripple)
  ffmpeg.py       Probing, Encoder-Wahl, Loudness, Audio nach numpy
  german.py       Stoppwörter, Füllwörter, Keyword-Bewertung
  ingest.py transcribe.py plan.py assets.py sfx.py stock.py render.py serve.py
  learn.py        Messwerte → style.json + Terminal-Report
  analyze/        je Modul genau eine Messung
    frames.py     Frames aus ffmpeg als numpy
    scenes.py     PySceneDetect
    motion.py     Optical Flow, Zerlegung in Zoom und Schwenk
    text.py       OCR, Overlays vs. Captions
    color.py      Histogramm, Sättigung, Kontrast, Farbtemperatur
    audio.py      Sprache/Nicht-Sprache, Transienten, Musik
    subject.py    Talking Head vs. B-Roll
  templates/element.html   die HTML/CSS-Animationen
  web/            die Oberfläche von 'serve'
```

## Wichtige Datenverträge

**`edit.json`** — `segments` sind die *behaltenen* Stücke: `source_in/out`
zeigen ins `ingest.mp4`, `t_in/out` in die fertige Zeitachse. Alle anderen
Elemente liegen in der **fertigen** Zeitachse. Wortzeiten in Captions sind
relativ zum Blockanfang. `schema_version` hochzählen, wenn sich das Format
ändert — `load_edit` weist alte Dateien sonst ab.

**`style.json`** — Größen mit `_rel` sind relativ zur **Bildhöhe**.
`per_10s` ist Dichte, nicht Anzahl.

**Pfade in der `edit.json`** — immer über `paths.resolve_asset()` auflösen:
Assets und B-Roll liegen im Projektordner, die SFX-Bibliothek im Repo-Wurzel.

## Fallen, die schon zugeschnappt sind

Alle drei sind teuer gefundene Fehler. Nicht zurückbauen:

* **Kein `fps`-Filter nach `concat`.** Hinter einem `concat` mit
  `zoompan`-Zweigen rechnet `fps` die Zeitbasis falsch um — aus 13 s wurden
  814 s. Die Bildrate wird **pro Zweig** vor dem Zoom gesetzt
  (`render.render_base`).
* **Optical Flow gewichtet.** Die Zerlegung in `analyze/motion.py` wird mit der
  lokalen Kantenstärke gewichtet. Ohne Gewichtung ziehen strukturlose Flächen
  (Wand, Himmel, Unschärfe) die Schätzung um ein Vielfaches nach unten: gegen
  eine Fahrt mit Sollwert 1.12 misst gewichtet 1.104, ungewichtet 1.042.
* **Transienten adaptiv suchen.** Ein globales Perzentil auf dem spektralen
  Fluss findet in dichter Sprache keinen einzigen Effekt (1 von 8 Markern);
  mit lokal gleitendem Median 6 von 8.

Weitere Stellen, an denen es leicht schiefgeht:

* Overlays werden im Template erst nach `document.fonts.ready` aufgebaut —
  sonst misst der Browser die Textkästen mit der Ersatzschrift aus.
* Die OCR läuft über zwei Bildkanäle (Luma und LAB-b). Gelber Text auf heller
  Fläche hat in Luma fast keinen Kontrast. Zusatzkanäle dürfen nur füllen, was
  der Luma-Kanal gar nicht gesehen hat — ihre Kästen sind unzuverlässig.
* **Positionen kommen aus der `edit.json`, nicht aus dem Asset-Manifest.** Das
  Manifest liefert nur die Cliplänge. Andersherum standen Overlays nach einem
  Schnitt an ihren alten Stellen oder fehlten ganz.
* Nach jeder Schnittoperation sind die gerenderten Assets veraltet.
  `assets.stale_elements()` sagt, welche — `render` warnt, die Oberfläche baut
  sie beim Rendern selbst neu.
* Einblendungen werden über **Lage und Größe** verfolgt, nicht über den Text.
  OCR-Ausgabe schwankt von Bild zu Bild und würde eine Einblendung sonst in
  mehrere zerlegen; Dichte und Standzeit wären dann Unsinn.

## Arbeitsweise

* **Auf einem kurzen Beispielvideo testen, bevor es weitergeht.** Das Material
  erzeugen `tests/make_fixture.py` und `tests/make_reference.py` lokal.
* **Messen, nicht behaupten.** Für Bild und Ton heißt „läuft durch" wenig.
  Prüf das Ergebnis: Frames ziehen und ansehen, Pegel messen, gegen die
  Sollwerte in `tests/check_learn.py` rechnen.
* Neue Messung in `learn`? Eine Prüfung in `tests/check_learn.py` dazu, mit
  einem Sollwert aus `tests/make_reference.py`.
* Fehlermeldungen auf Deutsch und mit dem nächsten Schritt darin
  („erst 'vidkit ingest' laufen lassen", „brew install …").
* Code und Kommentare auf Deutsch, ohne Umlaute in Bezeichnern. Kommentare
  erklären das Warum, nicht das Was.

## Umgebung

Entwickelt für macOS mit Apple Silicon, Python 3.11+, ffmpeg über Homebrew.
Läuft auch auf Linux/x86 — dann ohne VideoToolbox und ohne mlx-whisper, die
Rückfalloptionen greifen automatisch. `python -m vidkit doctor` zeigt, was da
ist.
