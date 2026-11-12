import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { loadFont as loadMono } from "@remotion/google-fonts/IBMPlexMono";
import { loadFont as loadHand } from "@remotion/google-fonts/ArchitectsDaughter";
import { FEED, PAGE_AT, T } from "./theme";

export const mono = loadMono("normal", { weights: ["400", "500", "600"], subsets: ["latin"] }).fontFamily;
export const hand = loadHand("normal", { weights: ["400"], subsets: ["latin"] }).fontFamily;

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** How far the paper has been fed, in pixels. */
export const usePaperY = (pages: number = PAGE_AT.length): number => {
  const f = useCurrentFrame();
  let y = 0;
  for (let i = 1; i < Math.min(pages, PAGE_AT.length); i++) {
    y += interpolate(f, [PAGE_AT[i] - FEED, PAGE_AT[i]], [0, T.H], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  }
  return y;
};

/** The continuous sheet: green bars, tractor-feed holes, a perforation between pages. */
export const Sheet: React.FC<{ pages: number; children: React.ReactNode }> = ({ pages, children }) => {
  const y = usePaperY(pages);
  const bands = [];
  for (let i = 1; i < (pages * T.H) / T.BAND; i += 2) {
    bands.push(<div key={i} style={{ position: "absolute", left: 0, top: i * T.BAND, width: T.W, height: T.BAND, background: T.band }} />);
  }
  const holes = [];
  for (let i = 0; i < (pages * T.H) / T.BAND; i++) {
    for (const x of [26, T.W - 26]) {
      holes.push(<circle key={`${i}-${x}`} cx={x} cy={i * T.BAND + T.BAND / 2} r={8} fill="#c9d0c4" />);
    }
  }
  const perforations = [];
  for (let p = 1; p < pages; p++) {
    perforations.push(<line key={p} x1={0} x2={T.W} y1={p * T.H} y2={p * T.H} stroke={T.rule} strokeWidth={2} strokeDasharray="2 7" />);
  }
  return (
    <AbsoluteFill style={{ backgroundColor: T.paper, overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 0, top: -y, width: T.W, height: pages * T.H }}>
        {bands}
        <svg width={T.W} height={pages * T.H} style={{ position: "absolute", left: 0, top: 0 }}>
          {holes}
          <line x1={52} x2={52} y1={0} y2={pages * T.H} stroke={T.rule} strokeWidth={1} />
          <line x1={T.W - 52} x2={T.W - 52} y1={0} y2={pages * T.H} stroke={T.rule} strokeWidth={1} />
          {perforations}
        </svg>
        {children}
      </div>
    </AbsoluteFill>
  );
};

type LineProps = {
  page: number;
  row: number; // line number on the page, 0-based; halves allowed
  at?: number; // frame (relative to the page start) at which the printer reaches this line
  x?: number;
  size?: number;
  weight?: number;
  color?: string;
  children: React.ReactNode;
};

/** One printed line. A line printer prints a whole line at once, so lines appear, they do not fade. */
export const Line: React.FC<LineProps> = ({ page, row, at = 0, x = T.X0, size = T.FONT, weight = 400, color = T.ink, children }) => {
  const f = useCurrentFrame();
  if (f < PAGE_AT[page] + at) return null;
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: page * T.H + row * T.LINE + (T.LINE - size * 1.25) / 2,
        fontFamily: mono,
        fontSize: size,
        lineHeight: 1.25,
        fontWeight: weight,
        color,
        whiteSpace: "pre",
        letterSpacing: 0,
      }}
    >
      {children}
    </div>
  );
};

/** A pen stroke that draws itself. Coordinates are page-relative. */
export const Stroke: React.FC<{ page: number; d: string; at: number; dur?: number; color?: string; width?: number }> = ({
  page, d, at, dur = 14, color = T.pen, width = 3.5,
}) => {
  const f = useCurrentFrame();
  const t = interpolate(f, [PAGE_AT[page] + at, PAGE_AT[page] + at + dur], [0, 1], { ...clamp, easing: Easing.out(Easing.quad) });
  if (t <= 0) return null;
  return (
    <svg width={T.W} height={T.H} style={{ position: "absolute", left: 0, top: page * T.H, overflow: "visible" }}>
      <path d={d} fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round"
        pathLength={1} strokeDasharray={1} strokeDashoffset={1 - t} opacity={0.92} />
    </svg>
  );
};

/** A roughly drawn loop around a rectangle, the way a reviewer circles something. */
export const loopPath = (x: number, y: number, w: number, h: number): string => {
  const cx = x + w / 2, cy = y + h / 2, rx = w / 2 + 14, ry = h / 2 + 9;
  return [
    `M ${cx - rx * 0.86} ${cy - ry * 0.62}`,
    `C ${cx - rx * 0.3} ${cy - ry * 1.5}, ${cx + rx * 0.9} ${cy - ry * 1.35}, ${cx + rx} ${cy - ry * 0.05}`,
    `C ${cx + rx * 1.06} ${cy + ry * 1.25}, ${cx - rx * 0.5} ${cy + ry * 1.3}, ${cx - rx} ${cy + ry * 0.25}`,
    `C ${cx - rx * 1.16} ${cy - ry * 0.75}, ${cx - rx * 0.45} ${cy - ry * 1.28}, ${cx - rx * 0.1} ${cy - ry * 1.08}`,
  ].join(" ");
};

/** Handwriting that is written left to right. */
export const Note: React.FC<{
  page: number; x: number; y: number; at: number; dur?: number; color?: string; size?: number; rotate?: number; children: React.ReactNode;
}> = ({ page, x, y, at, dur = 22, color = T.pen, size = 30, rotate = -2, children }) => {
  const f = useCurrentFrame();
  const t = interpolate(f, [PAGE_AT[page] + at, PAGE_AT[page] + at + dur], [0, 100], clamp);
  if (t <= 0) return null;
  return (
    <div
      style={{
        position: "absolute", left: x, top: page * T.H + y, fontFamily: hand, fontSize: size, lineHeight: 1.15, color,
        whiteSpace: "pre", transform: `rotate(${rotate}deg)`, transformOrigin: "left center",
        clipPath: `inset(-20% ${100 - t}% -20% 0)`,
      }}
    >
      {children}
    </div>
  );
};
