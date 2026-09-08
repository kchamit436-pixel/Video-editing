import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { FARBEN, GROESSE, SCHRIFT, rel } from "../stil";
import { useFeder } from "./feder";

export type ZaehlerProps = {
  von: number;
  bis: number;
  praefix: string;
  einheit: string;
  unterzeile: string;
  start: number;
  dauer: number;
  nachkommastellen: number;
};

// Die Zahl laeuft mit auslaufender Kurve hoch: schnell los, sanft ins Ziel.
// Linear zaehlen sieht nach Ladebalken aus, nicht nach Ergebnis.
export const Zaehler: React.FC<ZaehlerProps> = ({
  von,
  bis,
  praefix,
  einheit,
  unterzeile,
  start,
  dauer,
  nachkommastellen,
}) => {
  const frame = useCurrentFrame();
  const { height } = useVideoConfig();
  const auftritt = useFeder(start, "ueberschwingen");

  const wert = interpolate(frame, [start, start + dauer], [von, bis], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        fontFamily: SCHRIFT.familie,
        transform: `scale(${Math.max(0, auftritt)})`,
      }}
    >
      <div
        style={{
          fontSize: rel(height, GROESSE.zaehler_rel),
          fontWeight: SCHRIFT.fett,
          letterSpacing: "-0.03em",
          color: FARBEN.schrift,
          // Ohne Tabellenziffern zappelt die Zahl bei jedem Bild in der Breite.
          fontVariantNumeric: "tabular-nums",
          lineHeight: 1,
        }}
      >
        {praefix}
        {wert.toLocaleString("de-DE", {
          minimumFractionDigits: nachkommastellen,
          maximumFractionDigits: nachkommastellen,
        })}
        <span style={{ color: FARBEN.akzent }}>{einheit}</span>
      </div>
      <div
        style={{
          marginTop: rel(height, 0.018),
          fontSize: rel(height, GROESSE.kicker_rel),
          fontWeight: SCHRIFT.halbfett,
          letterSpacing: "0.2em",
          textTransform: "uppercase",
          color: FARBEN.gedaempft,
        }}
      >
        {unterzeile}
      </div>
    </AbsoluteFill>
  );
};
