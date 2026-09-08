// Alle Stilwerte an einer Stelle. Kein Element rechnet Farben, Groessen oder
// Federhaerten selbst aus — wer das Aussehen aendern will, aendert es hier.

export const FORMAT = {
  breite: 1080,
  hoehe: 1920,
  fps: 30,
} as const;

export const FARBEN = {
  grund: "#0B0D12",
  flaeche: "#161B24",
  schrift: "#F4F7FB",
  gedaempft: "#8C97A8",
  akzent: "#FFD230",
  aufAkzent: "#150F00",
} as const;

export const SCHRIFT = {
  familie:
    '"SF Pro Display", "Helvetica Neue", Helvetica, Arial, "DejaVu Sans", sans-serif',
  fett: 800,
  halbfett: 600,
  normal: 400,
} as const;

// Groessen relativ zur Bildhoehe — wie in der style.json des Hauptprojekts.
// So wirkt ein Element in 1080x1920 genauso wie in einer kleineren Vorschau.
export const GROESSE = {
  kicker_rel: 0.021,
  titel_rel: 0.062,
  punkt_rel: 0.036,
  caption_rel: 0.048,
  zaehler_rel: 0.15,
  drittel_rel: 0.03,
  rand_rel: 0.075,
} as const;

// Drei Federn reichen: weich blendet ein, knackig setzt einen Akzent,
// ueberschwingen laesst etwas hereinspringen und kurz nachwippen.
export const FEDERN = {
  weich: { damping: 30, mass: 1, stiffness: 90 },
  knackig: { damping: 14, mass: 0.7, stiffness: 180 },
  ueberschwingen: { damping: 9, mass: 0.8, stiffness: 200 },
} as const;

export type Federname = keyof typeof FEDERN;

// Bildhoehe mal Faktor. Einzige Stelle, an der aus einem _rel-Wert
// eine Pixelgroesse wird.
export const rel = (hoehe: number, faktor: number) => hoehe * faktor;
