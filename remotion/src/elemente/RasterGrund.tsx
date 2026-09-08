import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

// Dunkles Raster mit Schimmer aus der unteren Ecke. Die Linien sind leicht
// gekippt, damit sie nicht nach Tabelle aussehen, und das Licht wandert
// langsam — sonst wirkt der Grund tot, sobald vorne nichts passiert.
export const RasterGrund: React.FC<{
  neigung: number;
  teilung: number;
}> = ({ neigung, teilung }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const lauf = interpolate(frame, [0, durationInFrames], [0, 1]);

  const linie = "rgba(120, 200, 195, 0.10)";
  const glutX = interpolate(lauf, [0, 1], [8, 22]);
  const glutY = interpolate(lauf, [0, 1], [92, 78]);

  return (
    <AbsoluteFill style={{ backgroundColor: "#05100F", overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(65% 45% at ${glutX}% ${glutY}%, #1B6F68 0%, transparent 70%)`,
        }}
      />
      <AbsoluteFill
        style={{
          // Ueber die Diagonale vergroessert, damit die Drehung keine leeren
          // Ecken hinterlaesst.
          width: "160%",
          height: "160%",
          left: "-30%",
          top: "-30%",
          transform: `rotate(${neigung}deg)`,
          backgroundImage: `repeating-linear-gradient(0deg, ${linie} 0 1px, transparent 1px ${teilung}px), repeating-linear-gradient(90deg, ${linie} 0 1px, transparent 1px ${teilung}px)`,
        }}
      />
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(85% 65% at 50% 30%, transparent 0%, rgba(0,0,0,0.72) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};
