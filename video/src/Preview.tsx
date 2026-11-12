import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import raw from "./data.json";
import { Line, Note, Sheet, Stroke, loopPath, mono } from "./parts";
import { PAGE_AT, T } from "./theme";

type Row = { lang: string; name: string; ratio: number };
type Data = {
  draft: boolean;
  story: { kind: string; text: string }[];
  chart: { kernels: number; rows: Row[] };
  kernels: { key: string; title: string; vs_c: number }[];
  host: string;
  date: string;
  doom?: string[][];
  snake?: string[][];
  nbody?: string[][];
  mandelbrot?: string[][];
};
const data = raw as Data;

const CHAR = T.FONT * 0.6; // IBM Plex Mono advances 600 units per em
const lineY = (row: number) => row * T.LINE; // top of a printed line, page-relative
const number = (n: number) => n.toLocaleString("en-US");
const times = (r: number) => (r >= 100 ? `${Math.round(r)}x` : r >= 10 ? `${r.toFixed(0)}x` : `${r.toFixed(1)}x`);

// ---- page 1: what this is ------------------------------------------------------------
const Title: React.FC = () => {
  const miniScreens = [
    { label: "DOOM 3D Raycaster (.s)", grid: data.doom || [], x: 100 },
    { label: "Snake AI Engine (.s)", grid: data.snake || [], x: 380 },
    { label: "N-Body Gravity (.s)", grid: data.nbody || [], x: 660 },
    { label: "Mandelbrot 512x512 (.s)", grid: data.mandelbrot || [], x: 940 },
  ];
  const cw = 3.2;
  const ch = 3.6;

  return (
    <>
      <Line page={0} row={2.2} at={0} size={86} weight={600}>vibe-assembly</Line>
      <Line page={0} row={6.2} at={0} size={28}>Describe a function or app. An agent writes it in assembly.</Line>
      <Line page={0} row={7.8} at={8} size={28}>A 5-gate harness refuses to believe it until proven.</Line>
      <Stroke page={0} at={18} dur={12} d={`M ${T.X0 + 235} ${lineY(7.8) + 42} C ${T.X0 + 360} ${lineY(7.8) + 50}, ${T.X0 + 510} ${lineY(7.8) + 38}, ${T.X0 + 625} ${lineY(7.8) + 45}`} />
      <Line page={0} row={9.8} at={0} color={T.pen} weight={600} size={18}>
        CRC-32: 88.1x vs C   ·   Wordcount: 20.6x   ·   UTF-8: 11.8x   ·   DOOM 3D: 979k FPS   ·   12 Languages
      </Line>

      {/* 4 Pure-Assembly Visual Apps strip on Page 1 so frame 0 is immediately visual */}
      {miniScreens.map((ms) => (
        <div key={ms.label} style={{ position: "absolute", left: ms.x, top: 345 }}>
          <div style={{ fontFamily: mono, fontSize: 13, fontWeight: 600, color: T.ink, marginBottom: 4 }}>
            {ms.label}
          </div>
          <div style={{ width: 72 * cw, height: 48 * ch, background: "#0c0f18", border: `2px solid ${T.ink}`, overflow: "hidden" }}>
            <svg width={72 * cw} height={48 * ch}>
              {ms.grid.map((r, rIdx) =>
                r.map((hex, cIdx) => (
                  <rect key={`${rIdx}-${cIdx}`} x={cIdx * cw} y={rIdx * ch} width={cw + 0.35} height={ch + 0.35} fill={hex} />
                ))
              )}
            </svg>
          </div>
        </div>
      ))}

      <Line page={0} row={20.5} at={12} color={T.soft}>
        No compiler between the model and the machine. Zero trust without hold-out fuzzing &amp; guard pages.
      </Line>
    </>
  );
};

// ---- page 2: the first live run, as logged --------------------------------------------
const Story: React.FC = () => {
  const first = 2;
  const step = 11; // frames between printed lines
  const rowOf = (i: number) => first + i + (i >= 12 ? 1 : 0); // a blank line before round 2
  const reject = data.story.findIndex((l) => l.kind === "reject");
  const done = data.story.findIndex((l) => l.kind === "done");
  const rejectAt = 2 + reject * step;
  return (
    <>
      {data.story.map((l, i) => (
        <Line key={i} page={1} row={rowOf(i)} at={Math.max(0, (i - 2) * step)}
          weight={l.kind === "cmd" || l.kind === "reject" || l.kind === "done" ? 600 : 400}
          color={l.text.includes("FAIL") && l.kind === "log" ? T.soft : T.ink}>
          {l.text}
        </Line>
      ))}
      <Stroke page={1} at={rejectAt + 6} dur={18} color={T.red} width={4}
        d={loopPath(T.X0 - 4, lineY(rowOf(reject)) + 2, data.story[reject].text.length * CHAR + 8, T.LINE - 4)} />
      <Note page={1} x={760} y={lineY(rowOf(reject)) - 104} at={rejectAt + 22} dur={26} color={T.red} rotate={-3}>
        {"34,668 tests passed.\nThen this one."}
      </Note>
      <Note page={1} x={470} y={lineY(rowOf(13)) - 8} at={2 + 13 * step + 8} dur={22}>
        one constant: 252 to 251
      </Note>
      <Stroke page={1} at={2 + done * step + 8} dur={12}
        d={`M ${T.X0 + 46 * CHAR} ${lineY(rowOf(done)) + T.LINE + 3} C ${T.X0 + 52 * CHAR} ${lineY(rowOf(done)) + T.LINE + 9}, ${T.X0 + 62 * CHAR} ${lineY(rowOf(done)) + T.LINE - 2}, ${T.X0 + 70 * CHAR} ${lineY(rowOf(done)) + T.LINE + 5}`} />
    </>
  );
};

// ---- page 3: what a file has to survive -------------------------------------------------
const GATES: { name: string; lines: string[] }[] = [
  { name: "assemble", lines: ["for Apple M1 and later: nothing newer gets through"] },
  { name: "lint", lines: ["no libc, no global state, no system calls, one symbol"] },
  { name: "fuzz", lines: ["133,188 inputs against the reference C,", "every length from 0 to 17,000 bytes"] },
  { name: "guard pages", lines: ["one byte outside the buffer is a crash,", "reported with the source line and the registers"] },
  { name: "trampoline", lines: ["every scratch register poisoned before the call,", "every callee-saved one compared after it"] },
  { name: "hold-out", lines: ["then all of it again, twice, with seeds the agent never saw"] },
  { name: "stopwatch", lines: ["against clang -O3, every timed call re-checked"] },
];

const Tick: React.FC<{ x: number; y: number; at: number }> = ({ x, y, at }) => (
  <Stroke page={2} at={at} dur={7} width={4} d={`M ${x} ${y + 12} L ${x + 9} ${y + 22} L ${x + 28} ${y - 2}`} />
);

const Gates: React.FC = () => {
  let row = 4;
  let at = 0;
  const out: React.ReactNode[] = [];
  GATES.forEach((g, i) => {
    out.push(<Line key={`n${i}`} page={2} row={row} at={at} weight={600}>{g.name}</Line>);
    g.lines.forEach((text, j) => {
      out.push(<Line key={`l${i}-${j}`} page={2} row={row + j} at={at + j * 4} x={T.X0 + 15 * CHAR}>{text}</Line>);
    });
    out.push(<Tick key={`t${i}`} x={T.X0 - 40} y={lineY(row) + 2} at={at + 8} />);
    row += g.lines.length + 1;
    at += 16;
  });
  return (
    <>
      <Line page={2} row={1.6} at={0} size={32} weight={600}>What a file has to survive</Line>
      {out}
      <Note page={2} x={640} y={lineY(20.3)} at={at + 6} dur={30} rotate={-1.5}>
        the agent can run the checker, and nothing else
      </Note>
    </>
  );
};

// ---- page 4: the result ------------------------------------------------------------------
const Chart: React.FC = () => {
  const f = useCurrentFrame();
  const rows = data.chart.rows;
  const first = 4.5;
  const x0 = T.X0 + 13 * CHAR; // bars start after the 12-character label column
  const xMax = T.W - 52 - 150; // leave room for the value at the tip
  // Linear scale sized for the compiled and JIT-compiled languages; anything that would
  // not fit runs off the right edge of the paper, and says so.
  const fits = rows.filter((r) => r.ratio <= 40);
  const top = Math.max(...fits.map((r) => r.ratio), 2);
  const scaleMax = Math.ceil(top * 1.08);
  const px = (ratio: number) => ((xMax - x0) * ratio) / scaleMax;
  const tickStep = scaleMax <= 6 ? 1 : scaleMax <= 14 ? 2 : scaleMax <= 30 ? 5 : 10;
  const ticks: number[] = [];
  for (let t = 0; t <= scaleMax; t += tickStep) ticks.push(t);
  const base = PAGE_AT[3];
  const axisRow = first + rows.length + 0.4;
  return (
    <>
      <Line page={3} row={1.2} at={0} size={30} weight={600}>Time for one call, compared with the assembly</Line>
      <Line page={3} row={2.7} at={0} color={T.soft}>
        {`geometric mean over ${data.chart.kernels} kernels, same algorithm in every language; shorter is faster`}
      </Line>
      {f >= PAGE_AT[3] - 16 && (
        <svg width={T.W} height={T.H} style={{ position: "absolute", left: 0, top: 3 * T.H }}>
          {ticks.map((t) => (
            <line key={t} x1={x0 + px(t)} x2={x0 + px(t)} y1={lineY(first) - 6} y2={lineY(axisRow) + 4} stroke={T.rule} strokeWidth={1} />
          ))}
          {rows.map((r, i) => {
            const grow = interpolate(f, [base + i * 5, base + i * 5 + 14], [0.25, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const off = px(r.ratio) > xMax - x0 + 60;
            const full = off ? T.W - x0 + 40 : Math.max(px(r.ratio), 3);
            const w = full * grow;
            const y = lineY(first + i) + (T.LINE - 16) / 2;
            const fill = r.lang === "asm" ? T.pen : T.gray;
            // square at the baseline, 4px round at the data end
            const d = `M ${x0} ${y} h ${Math.max(w - 4, 0)} q 4 0 4 4 v 8 q 0 4 -4 4 h ${-Math.max(w - 4, 0)} z`;
            return w > 0 ? <path key={r.lang} d={d} fill={fill} /> : null;
          })}
        </svg>
      )}
      {rows.map((r, i) => {
        const at = i * 5;
        const off = px(r.ratio) > xMax - x0 + 60;
        return (
          <React.Fragment key={r.lang}>
            <Line page={3} row={first + i} at={0} weight={r.lang === "asm" ? 600 : 400}>{r.name}</Line>
            {off ? (
              <div style={{ position: "absolute", left: T.W - 52 - 340, top: 3 * T.H + lineY(first + i) + 2, opacity: f >= PAGE_AT[3] + at + 10 ? 1 : 0,
                fontFamily: mono, fontSize: T.FONT, lineHeight: `${T.LINE - 4}px`, color: T.ink, background: T.paper, padding: "0 10px", whiteSpace: "pre" }}>
                {`${times(r.ratio)}, off the page`}
              </div>
            ) : (
              <Line page={3} row={first + i} at={at + 10} x={x0 + Math.max(px(r.ratio), 3) + 12} weight={r.lang === "asm" ? 600 : 400}>
                {r.lang === "asm" ? "1.0x  written by the agent" : times(r.ratio)}
              </Line>
            )}
          </React.Fragment>
        );
      })}
      {ticks.filter((t) => t > 0).map((t) => (
        <Line key={t} page={3} row={axisRow + 0.3} at={0} x={x0 + px(t) - (String(t).length + 1) * CHAR * 0.5} color={T.soft}>{`${t}x`}</Line>
      ))}
      <Line page={3} row={axisRow + 2} at={rows.length * 5 + 14} color={T.soft}>
        {"against clang -O3:  " + data.kernels.slice(0, 3).map((k) => `${k.title} ${times(k.vs_c)}`).join("   ")}
      </Line>
      <Line page={3} row={axisRow + 3} at={rows.length * 5 + 20} color={T.soft}>
        {"                    " + data.kernels.slice(3).map((k) => `${k.title} ${times(k.vs_c)}`).join("   ")}
      </Line>
    </>
  );
};

// ---- page 5: where to get it ---------------------------------------------------------------
const Close: React.FC = () => {
  const langs = data.chart.rows.length;
  return (
    <>
      <Line page={4} row={4} at={0} size={44} weight={600}>{`${data.chart.kernels} kernels. ${langs} languages.`}</Line>
      <Line page={4} row={6.2} at={0} size={44} weight={600}>One answer each, checked.</Line>
      <Line page={4} row={10} at={8}>{`Measured on ${data.host}, ${data.date}.`}</Line>
      <Line page={4} row={11} at={14}>Every entry printed the same result as the C reference.</Line>
      <Line page={4} row={15} at={22} size={30} weight={600}>github.com/bizzono/vibe-assembly</Line>
      <Line page={4} row={17} at={28} color={T.soft}>MIT license. Harness, tasks, solutions and every benchmark entry.</Line>
      <Note page={4} x={690} y={lineY(19.4)} at={34} dur={26} size={34}>write the spec. skip the language.</Note>
    </>
  );
};

export const Preview: React.FC = () => (
  <Sheet pages={PAGE_AT.length}>
    <Title />
    <Story />
    <Gates />
    <Chart />
    <Close />
    {data.draft &&
      PAGE_AT.map((_, p) => (
        <div key={p} style={{ position: "absolute", left: 0, top: p * T.H + 8, width: T.W, textAlign: "center", fontFamily: mono, fontSize: 22, fontWeight: 600, color: T.red }}>
          DRAFT: placeholder numbers
        </div>
      ))}
  </Sheet>
);
