import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { FARBEN, GROESSE, SCHRIFT, rel } from "../stil";
import { useFeder } from "./feder";

export type Wortzeit = {
  wort: string;
  von: number;
  bis: number;
};

export type CaptionProps = {
  woerter: Wortzeit[];
  start: number;
};

// Wortzeiten sind Bilder relativ zum Blockanfang — dieselbe Abmachung wie in
// der edit.json des Hauptprojekts, damit ein Transkript ohne Umrechnung
// hierher passt.
export const Caption: React.FC<CaptionProps> = ({ woerter, start }) => {
  const frame = useCurrentFrame();
  const { height } = useVideoConfig();
  const auftritt = useFeder(start, "knackig");
  const jetzt = frame - start;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        padding: rel(height, GROESSE.rand_rel),
        fontFamily: SCHRIFT.familie,
      }}
    >
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: `${rel(height, 0.008)}px ${rel(height, 0.012)}px`,
          maxWidth: "88%",
          fontSize: rel(height, GROESSE.caption_rel),
          fontWeight: SCHRIFT.fett,
          textAlign: "center",
          opacity: Math.max(0, Math.min(1, auftritt)),
          transform: `translateY(${(1 - auftritt) * rel(height, 0.03)}px)`,
        }}
      >
        {woerter.map((eintrag, index) => {
          const aktiv = jetzt >= eintrag.von && jetzt < eintrag.bis;
          // Schon gesprochene Woerter bleiben stehen, aber gedaempft: der
          // Blick soll beim aktiven Wort bleiben, den Satz aber noch lesen.
          const gesprochen = jetzt >= eintrag.bis;

          return (
            <span
              key={index}
              style={{
                padding: `${rel(height, 0.004)}px ${rel(height, 0.011)}px`,
                borderRadius: rel(height, 0.009),
                backgroundColor: aktiv ? FARBEN.akzent : "transparent",
                color: aktiv
                  ? FARBEN.aufAkzent
                  : gesprochen
                    ? FARBEN.schrift
                    : FARBEN.gedaempft,
                transform: `scale(${aktiv ? 1.06 : 1})`,
              }}
            >
              {eintrag.wort}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
