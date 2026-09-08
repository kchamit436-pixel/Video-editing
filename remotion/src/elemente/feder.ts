import { spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FEDERN, type Federname } from "../stil";

// Federwert ab einem Startbild, 0 bis ungefaehr 1 — "ungefaehr", weil die
// harten Federn ueber 1 hinausschiessen und zurueckwippen. Genau das gibt
// der Bewegung ihr Gewicht, deshalb wird hier nicht geklemmt.
export const useFeder = (start = 0, art: Federname = "weich") => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return spring({
    frame: frame - start,
    fps,
    config: FEDERN[art],
  });
};

// Gleiche Feder, aber fuer viele Geschwister nacheinander: Element i startet
// um i * versatz Bilder spaeter.
export const useFederStaffel = (
  index: number,
  versatz: number,
  start = 0,
  art: Federname = "weich",
) => useFeder(start + index * versatz, art);
