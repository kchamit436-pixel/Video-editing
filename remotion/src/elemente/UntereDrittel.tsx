import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { FARBEN, GROESSE, SCHRIFT, rel } from "../stil";
import { useFeder } from "./feder";

export type UntereDrittelProps = {
  name: string;
  zeile: string;
  start: number;
};

// Der Kasten wird nicht eingeblendet, sondern aufgedeckt: eine Maske faehrt
// von links nach rechts. Deckkraft allein wirkt an dieser Stelle zaeh.
export const UntereDrittel: React.FC<UntereDrittelProps> = ({
  name,
  zeile,
  start,
}) => {
  const frame = useCurrentFrame();
  const { height, durationInFrames } = useVideoConfig();
  const auf = useFeder(start, "weich");
  const text = useFeder(start + 5, "knackig");

  const zu = interpolate(
    frame,
    [durationInFrames - 10, durationInFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const sichtbar = Math.max(0, Math.min(1, auf)) * (1 - zu);

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        padding: rel(height, GROESSE.rand_rel),
        paddingBottom: rel(height, 0.16),
        fontFamily: SCHRIFT.familie,
      }}
    >
      <div
        style={{
          alignSelf: "flex-start",
          display: "flex",
          alignItems: "stretch",
          backgroundColor: FARBEN.flaeche,
          borderRadius: rel(height, 0.012),
          overflow: "hidden",
          clipPath: `inset(0 ${(1 - sichtbar) * 100}% 0 0)`,
        }}
      >
        <div
          style={{
            width: rel(height, 0.007),
            backgroundColor: FARBEN.akzent,
          }}
        />
        <div
          style={{
            padding: `${rel(height, 0.018)}px ${rel(height, 0.03)}px`,
            opacity: Math.max(0, Math.min(1, text)),
          }}
        >
          <div
            style={{
              fontSize: rel(height, GROESSE.drittel_rel),
              fontWeight: SCHRIFT.fett,
              color: FARBEN.schrift,
              lineHeight: 1.15,
            }}
          >
            {name}
          </div>
          <div
            style={{
              marginTop: rel(height, 0.006),
              fontSize: rel(height, GROESSE.drittel_rel * 0.62),
              fontWeight: SCHRIFT.halbfett,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: FARBEN.gedaempft,
            }}
          >
            {zeile}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
