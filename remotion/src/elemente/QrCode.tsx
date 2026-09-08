import { useMemo } from "react";
import QRCode from "qrcode";

// Echter, scanbarer Code — keine gemalte Attrappe. Die Module werden als
// abgerundete Quadrate gezeichnet, weil das zur Bildsprache passt; die
// Ruhezone aussen bleibt frei, sonst liest ihn keine Kamera.
export const QrCode: React.FC<{
  inhalt: string;
  groesse: number;
  farbe: string;
  papier: string;
  eckenradius: number;
}> = ({ inhalt, groesse, farbe, papier, eckenradius }) => {
  const module = useMemo(() => {
    const code = QRCode.create(inhalt, { errorCorrectionLevel: "M" });
    const n = code.modules.size;
    const daten = code.modules.data;
    const punkte: { x: number; y: number }[] = [];
    for (let y = 0; y < n; y += 1) {
      for (let x = 0; x < n; x += 1) {
        if (daten[y * n + x]) punkte.push({ x, y });
      }
    }
    return { n, punkte };
  }, [inhalt]);

  const rand = 4;
  const seite = module.n + rand * 2;

  return (
    <svg
      width={groesse}
      height={groesse}
      viewBox={`0 0 ${seite} ${seite}`}
      shapeRendering="geometricPrecision"
    >
      <rect width={seite} height={seite} rx={2.2} fill={papier} />
      {module.punkte.map((p, i) => (
        <rect
          key={i}
          x={p.x + rand}
          y={p.y + rand}
          width={1.08}
          height={1.08}
          rx={eckenradius}
          fill={farbe}
        />
      ))}
      {/* Die vier Klammern sind Zierde, kein Teil des Codes. */}
      {[
        [rand - 1.6, rand - 1.6, 1, 1],
        [seite - rand + 1.6, rand - 1.6, -1, 1],
        [rand - 1.6, seite - rand + 1.6, 1, -1],
        [seite - rand + 1.6, seite - rand + 1.6, -1, -1],
      ].map(([x, y, sx, sy], i) => (
        <path
          key={`ecke-${i}`}
          d={`M ${x} ${y + sy * 3} L ${x} ${y + sy * 0.8} Q ${x} ${y} ${x + sx * 0.8} ${y} L ${x + sx * 3} ${y}`}
          fill="none"
          stroke={farbe}
          strokeWidth={0.55}
          strokeLinecap="round"
        />
      ))}
    </svg>
  );
};
