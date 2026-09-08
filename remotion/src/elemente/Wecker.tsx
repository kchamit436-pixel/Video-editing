import { Img, staticFile, useCurrentFrame } from "remotion";

// Gezeichneter Wecker im Zeitungsdruck-Look: schwarze Flaechen, Zifferblatt
// mit Rasterpunkten. Wer ein eigenes Freisteller-PNG hat, gibt es unter
// 'bild' an (Datei nach public/) — dann wird das genommen und nichts gemalt.
export const Wecker: React.FC<{
  groesse: number;
  stunde: number;
  minute: number;
  klingeln: number;
  bild?: string;
}> = ({ groesse, stunde, minute, klingeln, bild }) => {
  const frame = useCurrentFrame();

  // Klingeln ist eine schnelle Schwingung, die zu den Seiten abklingt.
  // Ohne Abklingen sieht es nach kaputtem Bildschirm aus, nicht nach Laerm.
  const schlag = Math.sin(frame * 1.9) * klingeln;
  const kippen = Math.sin(frame * 1.55) * klingeln * 0.6;

  if (bild) {
    return (
      <Img
        src={staticFile(bild)}
        style={{
          width: groesse,
          height: groesse,
          objectFit: "contain",
          transform: `translateX(${schlag}px) rotate(${kippen}deg)`,
        }}
      />
    );
  }

  const zeiger = (winkel: number, laenge: number, dicke: number) => {
    const rad = ((winkel - 90) * Math.PI) / 180;
    return (
      <line
        x1={50}
        y1={60}
        x2={50 + Math.cos(rad) * laenge}
        y2={60 + Math.sin(rad) * laenge}
        stroke="#0A0A0A"
        strokeWidth={dicke}
        strokeLinecap="round"
      />
    );
  };

  return (
    <svg
      width={groesse}
      height={groesse}
      viewBox="0 0 100 100"
      style={{ transform: `translateX(${schlag}px) rotate(${kippen}deg)` }}
    >
      <defs>
        <pattern id="raster" width="1.9" height="1.9" patternUnits="userSpaceOnUse">
          <circle cx="0.95" cy="0.95" r="0.42" fill="#0A0A0A" opacity="0.35" />
        </pattern>
        <radialGradient id="tiefe" cx="0.42" cy="0.36" r="0.75">
          <stop offset="0.55" stopColor="#0A0A0A" stopOpacity="0" />
          <stop offset="1" stopColor="#0A0A0A" stopOpacity="0.5" />
        </radialGradient>
      </defs>

      {/* Buegel zwischen den Glocken */}
      <path d="M 26 20 Q 50 2 74 20" fill="none" stroke="#0A0A0A" strokeWidth={3.4} />
      {/* Glocken */}
      <ellipse cx="25" cy="19" rx="12" ry="10" transform="rotate(-18 25 19)" fill="#0A0A0A" />
      <ellipse cx="75" cy="19" rx="12" ry="10" transform="rotate(18 75 19)" fill="#0A0A0A" />
      {/* Haemmerchen */}
      <rect x="47" y="16" width="6" height="9" rx="2" fill="#0A0A0A" />

      {/* Fuesse sitzen am Gehaeuse an, sonst schweben sie darunter */}
      <path d="M 30 84 L 17 98 L 33 93 Z" fill="#0A0A0A" />
      <path d="M 70 84 L 83 98 L 67 93 Z" fill="#0A0A0A" />

      {/* Gehaeuse und Zifferblatt */}
      <circle cx="50" cy="60" r="35" fill="#0A0A0A" />
      <circle cx="50" cy="60" r="28.5" fill="#FBFBF7" />
      <circle cx="50" cy="60" r="28.5" fill="url(#raster)" />
      <circle cx="50" cy="60" r="28.5" fill="url(#tiefe)" />
      <circle cx="50" cy="60" r="26" fill="none" stroke="#0A0A0A" strokeWidth={0.7} />

      {Array.from({ length: 12 }, (_, i) => {
        const winkel = ((i + 1) / 12) * Math.PI * 2 - Math.PI / 2;
        return (
          <text
            key={i}
            x={50 + Math.cos(winkel) * 21.5}
            y={60 + Math.sin(winkel) * 21.5 + 2.6}
            textAnchor="middle"
            fontSize="6.4"
            fontFamily='"Times New Roman", Georgia, serif'
            fill="#0A0A0A"
          >
            {i + 1}
          </text>
        );
      })}

      {zeiger((stunde % 12) * 30 + minute * 0.5, 13, 2.6)}
      {zeiger(minute * 6, 19.5, 1.9)}
      <circle cx="50" cy="60" r="2.1" fill="#0A0A0A" />
    </svg>
  );
};
