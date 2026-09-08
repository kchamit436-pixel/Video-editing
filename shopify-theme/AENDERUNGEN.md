# Was geändert wurde — sleepzlab.com, Produktseite SomaBand

Stand 08.09.2026. Bitte aufheben: Nach einem Theme-Update kann es sein,
dass Änderungen an Theme-eigenen Dateien überschrieben werden.

## Geändert: `sections/somaband.liquid`

Das ist eine **eigene Datei**, kein Bestandteil von Horizon. Ein
Theme-Update fasst sie **nicht** an. Die Änderungen bleiben also erhalten.

Was geändert wurde:

| # | Änderung | Warum |
|---|---|---|
| 1 | `<style>`-Block steht jetzt vor dem Markup statt dahinter | Der Browser baute die Seite sonst einmal ungestaltet auf und rechnete danach alles neu |
| 2 | Unsichtbare Arbeit läuft erst nach dem ersten gezeichneten Bild | Reveal-Effekte, Countdown-Takt, Lieferzeit-Datum, Karussell-Punkte, Sticky-Leiste blockierten vorher den Seitenaufbau |
| 3 | Galerie lädt die Nachbarbilder erst nach dem ersten Bild vor | Vorher liefen drei grosse Bilder gleichzeitig los; das sichtbare Bild musste sich die Leitung teilen |
| 4 | Experten-Wall klont ihre Karten erst kurz vor dem Sichtfeld | 20 Karten wurden vorher beim Seitenaufbau gebaut, obwohl sie ganz unten stehen |
| 5 | `content-visibility` auf der Experten-Wall, `will-change` entfernt | Der Browser rechnet die Wall unterhalb des Bildschirms gar nicht erst |

**Nicht angefasst:** Texte, Bilder, Farben, Abstände, Reihenfolge der
Abschnitte, Warenkorb, Checkout, Sternify, Tracking, Cookie-Banner.
Das Markup ist gegenüber dem Ausgangsstand zeichengleich.

## Nicht geändert, aber gefunden

Diese Punkte liegen ausserhalb der einen Datei und sind offen:

1. **`snippets/scripts.liquid`** lädt rund 30 Programmdateien auf *jeder*
   Seite, etwa 380 KB. Davon sind auf Produktseiten rund **177 KB in 23
   Dateien** nachweislich unbenutzt (`slideshow.js`, `product-form.js`,
   `product-card.js`, `variant-picker.js` und weitere), weil alle
   Produkt-Templates Horizons eigene Produkt-Section auf „deaktiviert"
   stehen haben. Das ist der grösste verbliebene Hebel für die Blockierzeit.
   *Achtung: Diese Datei gehört Horizon — ein Theme-Update setzt sie zurück.*

2. **Google Fonts hängt im Footer** (`sections/footer-group.json`, Block
   „custom_liquid"): ein `<link rel="stylesheet">` auf
   `fonts.googleapis.com` mit sechs Schriftschnitten, mitten im Seiteninhalt.
   Das hält das Zeichnen an. Inter wird dadurch doppelt geladen — einmal von
   Google für den Footer, einmal von Shopify für den Header.

3. **`layout/theme.liquid`**: die Laufschrift oben hängt an
   `window.addEventListener('resize', setupTopbar)` ohne Bremse. `setupTopbar`
   misst Breiten aus und schreibt zurück — auf dem Handy löst schon das
   Ein- und Ausblenden der Browserleiste beim Scrollen ein `resize` aus.
   *Auch diese Datei gehört Horizon.*

4. **`assets/base.css`**, 104 KB, hält das Zeichnen an. Aufteilen wäre ein
   echter Umbau mit echtem Risiko.
