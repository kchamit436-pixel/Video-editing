import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { FARBEN } from "../stil";

// Ruhiger Grund: ein Farbverlauf, der langsam wandert, plus Vignette.
// Absichtlich traege — er soll das Element im Vordergrund nicht anfassen.
export const Hintergrund: React.FC<{
  akzent?: string;
}> = ({ akzent = FARBEN.akzent }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const wanderung = interpolate(frame, [0, durationInFrames], [0, 1]);
  const x = interpolate(wanderung, [0, 1], [35, 65]);
  const y = interpolate(wanderung, [0, 1], [28, 20]);

  return (
    <AbsoluteFill style={{ backgroundColor: FARBEN.grund }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(70% 45% at ${x}% ${y}%, ${akzent}22 0%, transparent 70%)`,
        }}
      />
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(90% 60% at 50% 100%, #00000000 0%, #000000AA 100%)",
        }}
      />
    </AbsoluteFill>
  );
};
