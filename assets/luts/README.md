# LUTs — Farbe fuer die Shorts

Drei fertige `.cube`-Dateien plus das Werkzeug, mit dem sie entstehen.
Erzeugt aus `looks.json` durch `tools/make_lut.py`.

| Datei | Wofuer |
| --- | --- |
| `haut_neutral.cube` | Sicherer Grundlook. Haut bleibt Haut. Im Zweifel dieser. |
| `warm_marke.cube` | Waermer, satter, Schatten blaugruen. Der uebliche Werbelook. |
| `kuehl_klar.cube` | Kuehl, klar, mehr Kontrast, weniger Farbe. |

## Was eine LUT kann — und was nicht

Eine LUT ist eine Tabelle "Farbe rein, Farbe raus". Sie sieht immer nur ein
einzelnes Pixel, nie das Bild.

**Kann sie:** Weissabgleich, Kontrast, Saettigung, Teiltonung, Schwarzpunkt.

**Kann sie nicht:** Hintergrund unscharf machen, Vorder- und Hintergrund
verschieden behandeln, aufhellen wo das Gesicht ist, Lichtsetzung retten. Dafuer
muss das Bild in Ebenen zerlegt werden — siehe unten.

## In CapCut anwenden

Clip auswaehlen, im Anpassen-Bereich nach **LUT** suchen, eigene Datei
importieren, `.cube` laden. Die Beschriftung wechselt je nach CapCut-Version
zwischen "LUT", "Anpassen" und "Filter — Importieren".

Findet deine Version keinen LUT-Import, backe die Farbe vorher mit ffmpeg ins
Material und schneide danach:

```
ffmpeg -i aufnahme.mp4 -vf lut3d=assets/luts/haut_neutral.cube \
       -c:v hevc_videotoolbox -q:v 60 -c:a copy gegradet.mp4
```

## Hintergrund unscharf, Person scharf

Das ist Freistellen, keine Farbkorrektur. In CapCut in dieser Reihenfolge:

1. Clip duplizieren, sodass er zweimal uebereinander liegt.
2. Auf der **unteren** Spur: Unschaerfe als Effekt, kraeftig.
3. Auf der **oberen** Spur: automatisches Freistellen der Person.
4. LUT auf **beide** Spuren legen, sonst haben Vorder- und Hintergrund
   verschiedene Farben und der Schnitt faellt auf.

Das automatische Freistellen franst an Haaren und Haenden aus. Ruhig sitzen
hilft mehr als jede Nachbesserung.

## Selbst nachstellen

Zahlen stehen in `looks.json`, nicht im Code. Aendern, dann:

```
python3 tools/make_lut.py --alle
```

Vorher/Nachher auf einem eigenen Standbild ansehen, ohne CapCut zu oeffnen:

```
python3 tools/make_lut.py --vorschau standbild.jpg --look warm_marke
```

Die wichtigsten Regler:

| Name | Wirkung |
| --- | --- |
| `belichtung` | Blendenstufen. 0.1 ist wenig, 0.5 ist viel. |
| `temperatur` | Plus waermer, minus kuehler. |
| `schwarzpunkt` | Hebt die Schatten an. Der halbe Unterschied zwischen Handyvideo und gegradet. |
| `kontrast` | Anteil der S-Kurve, 0 bis 1. |
| `pivot` | Wo die Kurve dreht. Unter 0.5, damit das Gesicht nicht mit aufgehellt wird. |
| `saettigung` | 1.0 ist unveraendert. |
| `dynamik` | Laesst ohnehin bunte Stellen in Ruhe. |
| `hautschutz` | Nimmt die Saettigung genau dort zurueck, wo Haut ist. Hoch lassen. |

## Geprueft

`tools/make_lut.py` schreibt die Tabelle, liest sie zurueck und rechnet gegen
die direkte Rechnung: Abweichung unter 0.006 bei 33 Stuetzstellen. Der Graukeil
bleibt in allen drei Looks monoton, Schwarz und Weiss laufen nicht zu.
