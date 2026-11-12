import React from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";
import raw from "./data.json";
import { hand, Line, loopPath, mono, Note, Sheet, Stroke } from "./parts";
import { T } from "./theme";

type TokenRow = {
  id: string;
  name: string;
  loc: number;
  tokens: number;
  oneshot_usd: number;
  agent_usd: number;
  total_ms: number;
  geomean: number;
};

type SoftBench = {
  id: string;
  title: string;
  subtitle: string;
  file: string;
  metric: string;
  asm_ms: number;
  c_ms: number;
  js_ms: number;
  py_ms: number;
  vs_c: number;
  vs_py: number;
};

const data = raw as typeof raw & {
  tokens: TokenRow[];
  mandelbrot: string[][];
  doom: string[][];
  snake: string[][];
  nbody: string[][];
  software_benches: SoftBench[];
};

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const rowY = (row: number) => row * T.LINE + T.LINE / 2;

export const SECTION_FRAMES = 180;

/**
 * 1. OneShotAnim: Animates the 1-shot assembly workflow (base64_encode)
 *    from C prototype -> NEON vector assembly -> 5 verification gates -> 23.7 GB/s binary.
 */
export const OneShotAnim: React.FC = () => {
  const f = useCurrentFrame();

  const codeLines = [
    { at: 0, text: "// Load & deinterleave 48 B (16x3)", col: T.soft },
    { at: 4, text: "ld3  {v0.16b-v2.16b}, [x0], #48", col: T.pen },
    { at: 8, text: "// Split 24-bit triples -> 6-bit", col: T.soft },
    { at: 12, text: "ushr v3.16b, v0.16b, #2", col: T.ink },
    { at: 16, text: "ushr v4.16b, v1.16b, #4", col: T.ink },
    { at: 20, text: "sli  v4.16b, v0.16b, #4", col: T.ink },
    { at: 24, text: "ushr v5.16b, v2.16b, #6", col: T.ink },
    { at: 28, text: "sli  v5.16b, v1.16b, #2", col: T.ink },
    { at: 32, text: "and  v6.16b, v2.16b, v20.16b", col: T.ink },
    { at: 36, text: "// 64-byte alphabet LUT in 1 cycle", col: T.soft },
    { at: 40, text: "tbl  v3.16b, {v16.16b-v19.16b}, v3.16b", col: T.pen },
    { at: 44, text: "// Interleave & store 64 Base64 chars", col: T.soft },
    { at: 48, text: "st4  {v3.16b-v6.16b}, [x2], #64", col: T.pen },
  ];

  const gates = [
    { at: 18, title: "GATE 1: Static Source Lint", detail: "141 insns · no svc/brk · no .data" },
    { at: 28, title: "GATE 2: Object Symbol Hygiene", detail: "exports _base64_encode · 0 undef" },
    { at: 38, title: "GATE 3: ABI Canary Trampoline", detail: "x19-x29, d8-d15, sp & red zone ok" },
    { at: 48, title: "GATE 4: PROT_NONE Guard Pages", detail: "1B before/after unmapped pages" },
    { at: 58, title: "GATE 5: Hold-Out Fuzzing", detail: "194,840 cases (2 fresh seeds) PASS" },
  ];

  return (
    <Sheet pages={1}>
      <Line page={0} row={1.5} at={0} weight={600}>
        ONE-SHOT ASSEMBLY WALKTHROUGH: C PROTOTYPE TO 23.7 GB/s NEON KERNEL
      </Line>
      <Line page={0} row={2.5} at={0} color={T.soft} size={18}>
        Task: base64_encode   |   Solved in Round 1 (5.6 min)   |   194,840 hold-out test cases
      </Line>

      {/* Left Column: Spec + Command + Speedup Table */}
      <Line page={0} row={4.5} at={0} x={84} weight={600} size={18} color={T.pen}>
        1. THE C CONTRACT
      </Line>
      <Line page={0} row={5.5} at={0} x={84} size={16}>
        {"size_t base64_encode("}
      </Line>
      <Line page={0} row={6.3} at={0} x={84} size={16}>
        {"  const uint8_t *src,"}
      </Line>
      <Line page={0} row={7.1} at={0} x={84} size={16}>
        {"  size_t n, uint8_t *dst);"}
      </Line>

      <Line page={0} row={9.0} at={0} x={84} weight={600} size={18} color={T.pen}>
        2. ONE COMMAND TO SOLVE
      </Line>
      <Line page={0} row={10.0} at={0} x={84} weight={600} size={17}>
        $ vibeasm run base64_encode
      </Line>

      <Line page={0} row={12.0} at={20} x={84} weight={600} size={18} color={T.pen}>
        3. MEASURED SPEEDUP vs C -O3
      </Line>
      <Line page={0} row={13.0} at={26} x={84} size={16}>
        {"24 B   input :  2.97x faster"}
      </Line>
      <Line page={0} row={13.9} at={32} x={84} size={16}>
        {"255 B  input :  5.27x faster"}
      </Line>
      <Line page={0} row={14.8} at={38} x={84} size={16}>
        {"4 KiB  input :  5.75x faster"}
      </Line>
      <Line page={0} row={15.7} at={44} x={84} size={16}>
        {"1 MiB  input :  5.84x (23.7 GB/s)"}
      </Line>
      <Line page={0} row={17.0} at={52} x={84} weight={600} size={18}>
        {"GEOMEAN      :  4.79x vs clang -O3"}
      </Line>

      {/* Center Column: One-Shot NEON Assembly */}
      <Line page={0} row={4.5} at={0} x={430} weight={600} size={18} color={T.pen}>
        WHAT THE LLM WROTE (64 B/loop)
      </Line>
      {codeLines.map((ln, idx) => (
        <Line key={idx} page={0} row={5.6 + idx * 0.9} at={ln.at} x={430} size={15.5} color={ln.col} weight={ln.col === T.pen ? 600 : 400}>
          {ln.text}
        </Line>
      ))}

      <Line page={0} row={18.0} at={54} x={430} weight={600} size={16}>
        $ clang -O3 app.c solutions/arm64-darwin/*.s -o app
      </Line>

      {/* Right Column: The 5 Verification Gates */}
      <Line page={0} row={4.5} at={0} x={855} weight={600} size={18} color={T.pen}>
        5 GATES BEFORE INSTALL
      </Line>
      {gates.map((g, idx) => {
        const active = f >= g.at;
        const gy = (5.7 + idx * 2.3) * T.LINE;
        return (
          <div
            key={idx}
            style={{
              position: "absolute",
              left: 855,
              top: gy,
              width: 350,
              height: 54,
              background: active ? "#e4efe0" : "#eef0e8",
              border: `2px solid ${active ? T.pen : T.rule}`,
              borderRadius: 6,
              padding: "6px 10px",
              fontFamily: mono,
            }}
          >
            <div style={{ fontSize: 14.5, fontWeight: 600, color: active ? T.ink : T.soft }}>
              {active ? `[PASS] ${g.title}` : `[....] ${g.title}`}
            </div>
            <div style={{ fontSize: 13, color: T.soft, marginTop: 2 }}>{g.detail}</div>
          </div>
        );
      })}

      {/* Reviewer annotations */}
      <Stroke page={0} at={64} d={loopPath(80, rowY(17.0) - 12, 315, 28)} />
      <Note page={0} x={84} y={rowY(19.2)} at={72} size={27} rotate={-1.5}>
        Solved in 1 round — drop straight into C, Rust, or Zig!
      </Note>
      <Note page={0} x={855} y={rowY(18.5)} at={84} size={25} rotate={-2}>
        48 B in -&gt; 64 B out per cycle
      </Note>
    </Sheet>
  );
};

/**
 * 2. MandelbrotAnim: Animates the 100% pure-assembly standalone binary racing
 *    C, Node.js, and Python to render the 72x48 truecolor Mandelbrot fractal.
 */
export const MandelbrotAnim: React.FC = () => {
  const f = useCurrentFrame();
  const grid = data.mandelbrot || [];
  const rows = grid.length || 48;
  const cols = (grid[0] && grid[0].length) || 72;

  // Assembly (2.17ms) completes by frame 22 (and starts with 16 rows already visible at frame 0!)
  // C (18.98ms, 8.8x) scans across frames 0 -> 135
  // Python (469ms, 216.6x) crawls down the top 20% of the image
  const asmRows = Math.floor(interpolate(f, [0, 22], [16, rows], clamp));
  const cRows = Math.floor(interpolate(f, [0, 135], [2, rows], clamp));
  const pyRows = Math.floor(interpolate(f, [0, 175], [1, Math.round(rows * 0.2)], clamp));

  const cellW = 7.2;
  const cellH = 8.5;
  const gx0 = 84;
  const gy0 = 152;

  const racers = [
    { name: "ARM64 Assembly (.s)", ms: "2.17 ms", ratio: "1.0x", progress: interpolate(f, [0, 22], [0.35, 1], clamp), col: T.pen, bold: true },
    { name: "Rust (rustc -O3)", ms: "18.84 ms", ratio: "8.7x", progress: interpolate(f, [0, 134], [0.05, 1], clamp), col: T.ink, bold: false },
    { name: "C (clang -O3)", ms: "18.98 ms", ratio: "8.8x", progress: interpolate(f, [0, 135], [0.05, 1], clamp), col: T.ink, bold: false },
    { name: "Node.js (V8 JIT)", ms: "19.30 ms", ratio: "8.9x", progress: interpolate(f, [0, 138], [0.05, 1], clamp), col: T.ink, bold: false },
    { name: "Python 3.15", ms: "469.0 ms", ratio: "216.6x", progress: interpolate(f, [0, 175], [0.02, 0.2], clamp), col: T.red, bold: false },
  ];

  return (
    <Sheet pages={1}>
      <Line page={0} row={1.5} at={0} weight={600}>
        PURE-ASSEMBLY APPLICATION: ZERO C FILES, SINGLE-SYSCALL MANDELBROT
      </Line>
      <Line page={0} row={2.5} at={0} color={T.soft} size={18}>
        $ clang examples/standalone_mandelbrot.s -o mandelbrot &amp;&amp; ./mandelbrot
      </Line>

      <Line page={0} row={4.1} at={0} x={gx0} weight={600} size={17} color={T.pen}>
        LIVE STDOUT CAPTURE (72x48 24-bit ANSI)
      </Line>
      <div
        style={{
          position: "absolute",
          left: gx0,
          top: gy0,
          width: cols * cellW,
          height: rows * cellH,
          background: "#0c0f18",
          border: `2px solid ${T.ink}`,
          overflow: "hidden",
        }}
      >
        <svg width={cols * cellW} height={rows * cellH}>
          {grid.slice(0, asmRows).map((r, rIdx) =>
            r.map((hex, cIdx) => (
              <rect
                key={`${rIdx}-${cIdx}`}
                x={cIdx * cellW}
                y={rIdx * cellH}
                width={cellW + 0.4}
                height={cellH + 0.4}
                fill={hex}
              />
            ))
          )}
          {cRows < rows && (
            <g>
              <line x1={0} x2={cols * cellW} y1={cRows * cellH} y2={cRows * cellH} stroke="#ffbd2e" strokeWidth={2.5} />
              <rect x={cols * cellW - 148} y={Math.max(2, cRows * cellH - 18)} width={144} height={16} fill="#161b22" opacity={0.9} />
              <text x={cols * cellW - 76} y={Math.max(14, cRows * cellH - 6)} fill="#ffbd2e" fontSize={11} fontFamily={mono} textAnchor="middle">
                C / Rust / JS scanline
              </text>
            </g>
          )}
          <g>
            <line x1={0} x2={cols * cellW} y1={pyRows * cellH} y2={pyRows * cellH} stroke="#ff5f56" strokeWidth={2.5} />
            <rect x={6} y={Math.min(rows * cellH - 20, pyRows * cellH + 3)} width={140} height={16} fill="#161b22" opacity={0.9} />
            <text x={76} y={Math.min(rows * cellH - 8, pyRows * cellH + 15)} fill="#ff5f56" fontSize={11} fontFamily={mono} textAnchor="middle">
              Python (216.6x slower)
            </text>
          </g>
        </svg>
      </div>

      {/* Right panel: Inside the assembly binary + live race bars */}
      <Line page={0} row={4.1} at={0} x={640} weight={600} size={17} color={T.pen}>
        INSIDE standalone_mandelbrot.s
      </Line>
      <Line page={0} row={5.1} at={0} x={640} size={15.5}>
        {"fmov   d2, #0.25"}
      </Line>
      <Line page={0} row={5.95} at={0} x={640} size={15.5}>
        {"fsub   d3, d0, d2          // cr - 0.25"}
      </Line>
      <Line page={0} row={6.8} at={0} x={640} size={15.5}>
        {"fmadd  d5, d3, d3, d4      // cardioid q"}
      </Line>
      <Line page={0} row={7.65} at={0} x={640} size={15.5} color={T.pen} weight={600}>
        {"b.le   Lpoint_in_set       // skip 200-iter!"}
      </Line>
      <Line page={0} row={8.5} at={0} x={640} size={15.5}>
        {"mov    x0, #1              // stdout fd"}
      </Line>
      <Line page={0} row={9.35} at={0} x={640} size={15.5} color={T.pen} weight={600}>
        {"bl     _write              // 1 syscall flush"}
      </Line>

      <Line page={0} row={11.0} at={0} x={640} weight={600} size={17} color={T.pen}>
        512x512 BENCHMARK RACE (sum = 9,985,499)
      </Line>
      {racers.map((r, i) => {
        const ry = 12.1 + i * 1.35;
        const barW = Math.max(6, Math.round(r.progress * 210));
        return (
          <React.Fragment key={r.name}>
            <Line page={0} row={ry} at={0} x={640} size={15} weight={r.bold ? 600 : 400} color={r.col}>
              {r.name.padEnd(21)}
            </Line>
            <div
              style={{
                position: "absolute",
                left: 850,
                top: ry * T.LINE + 7,
                width: barW,
                height: 15,
                background: r.col,
                borderRadius: 3,
              }}
            />
            <Line page={0} row={ry} at={0} x={1075} size={14.5} weight={r.bold ? 600 : 400} color={r.col}>
              {`${r.ms} (${r.ratio})`}
            </Line>
          </React.Fragment>
        );
      })}

      <Note page={0} x={84} y={rowY(19.2)} at={28} size={25} rotate={-1}>
        Zero C runtime: 100% ARM64 instructions + 1 _write syscall
      </Note>
      <Note page={0} x={84} y={rowY(20.8)} at={48} size={25} color={T.red} rotate={-0.8}>
        Assembly finishes in 2.17 ms — before Python draws row 1!
      </Note>
    </Sheet>
  );
};

/**
 * 3. SoftwareBenchAnim: Shows 4 real-time software & game engines written in 100% ARM64 Assembly
 *    (3D DOOM Raycaster, Autonomous Snake AI, N-Body Galaxy Physics, Mandelbrot Renderer)
 *    side-by-side with live benchmarks vs C (-O3), Node.js (V8), and Python.
 */
export const SoftwareBenchAnim: React.FC = () => {
  const f = useCurrentFrame();
  const screens = [
    { title: "1. 3D DOOM RAYCASTER (doom.s)", grid: data.doom || [], x: 84, y: 128, tag: "979k FPS · 15.2x vs C" },
    { title: "2. AUTONOMOUS SNAKE AI (snake_ai.s)", grid: data.snake || [], x: 356, y: 128, tag: "212M ticks/s · NEON saba" },
    { title: "3. N-BODY GALAXY SIM (nbody_sim.s)", grid: data.nbody || [], x: 84, y: 398, tag: "2.68B pairs/s · frsqrte" },
    { title: "4. MANDELBROT 512x512 (mandelbrot.s)", grid: data.mandelbrot || [], x: 356, y: 398, tag: "461 FPS · 8.75x vs C" },
  ];

  const benches = data.software_benches || [];
  const cw = 3.5;
  const ch = 4.2;

  return (
    <Sheet pages={1}>
      <Line page={0} row={1.3} at={0} weight={600}>
        PURE-ASSEMBLY GAMES &amp; ENGINES: DOOM, SNAKE AI, N-BODY &amp; FRACTALS
      </Line>
      <Line page={0} row={2.2} at={0} color={T.soft} size={17.5}>
        Four 100% standalone ARM64 assembly binaries (zero C files) + live engine benchmarks
      </Line>

      {/* Left 2x2 Arcade & Simulation Grid */}
      {screens.map((sc, idx) => {
        const revealRows = Math.floor(interpolate(f, [idx * 6, idx * 6 + 24], [24, 48], clamp));
        return (
          <div key={sc.title} style={{ position: "absolute", left: sc.x, top: sc.y }}>
            <div style={{ fontFamily: mono, fontSize: 11.5, fontWeight: 600, color: T.pen, marginBottom: 4 }}>
              {sc.title}
            </div>
            <div
              style={{
                width: 72 * cw,
                height: 48 * ch,
                background: "#0c0f18",
                border: `2px solid ${T.ink}`,
                position: "relative",
                overflow: "hidden",
              }}
            >
              <svg width={72 * cw} height={48 * ch}>
                {sc.grid.slice(0, revealRows).map((r, rIdx) =>
                  r.map((hex, cIdx) => (
                    <rect
                      key={`${rIdx}-${cIdx}`}
                      x={cIdx * cw}
                      y={rIdx * ch}
                      width={cw + 0.35}
                      height={ch + 0.35}
                      fill={hex}
                    />
                  ))
                )}
              </svg>
              <div
                style={{
                  position: "absolute",
                  right: 4,
                  bottom: 4,
                  background: "rgba(13,17,23,0.88)",
                  color: "#7ee787",
                  fontFamily: mono,
                  fontSize: 10.5,
                  fontWeight: 600,
                  padding: "2px 6px",
                  borderRadius: 3,
                  border: "1px solid #30363d",
                }}
              >
                {sc.tag}
              </div>
            </div>
          </div>
        );
      })}

      {/* Right Panel: Software & Game Benchmark Table */}
      <Line page={0} row={3.9} at={0} x={636} weight={600} size={17} color={T.pen}>
        SOFTWARE &amp; GAME ENGINE BENCHMARKS (LOWER MS = FASTER)
      </Line>

      {benches.map((b, idx) => {
        const topRow = 5.1 + idx * 3.6;
        const grow = interpolate(f, [idx * 10, idx * 10 + 30], [0.25, 1], { ...clamp, easing: Easing.out(Easing.cubic) });

        const entries = [
          { label: "ARM64 Assembly", ms: b.asm_ms, mult: "1.0x", w: 16, col: T.pen, bold: true },
          { label: "C (clang -O3)", ms: b.c_ms, mult: `${b.vs_c}x`, w: Math.min(180, Math.round(16 * Math.max(1.3, Math.min(12, b.vs_c)) * grow)), col: T.ink, bold: false },
          { label: "Node.js (V8)", ms: b.js_ms, mult: `${(b.js_ms / b.asm_ms).toFixed(1)}x`, w: Math.min(200, Math.round(22 * Math.max(1.6, Math.min(14, b.js_ms / b.asm_ms)) * grow)), col: T.gray, bold: false },
          { label: "Python 3.15", ms: b.py_ms, mult: `${b.vs_py}x`, w: Math.round(220 * grow), col: T.red, bold: false },
        ];

        return (
          <React.Fragment key={b.id}>
            <Line page={0} row={topRow} at={0} x={636} weight={600} size={14.5} color={T.ink}>
              {`${b.title} (${b.subtitle.split(" (")[0]})`}
            </Line>
            {entries.map((e, eIdx) => {
              const r = topRow + 0.72 + eIdx * 0.62;
              return (
                <React.Fragment key={e.label}>
                  <Line page={0} row={r} at={0} x={644} size={13.5} weight={e.bold ? 600 : 400} color={e.col}>
                    {e.label}
                  </Line>
                  <div
                    style={{
                      position: "absolute",
                      left: 790,
                      top: r * T.LINE + 8,
                      width: e.w,
                      height: 11,
                      background: e.col,
                      borderRadius: 2,
                    }}
                  />
                  <Line page={0} row={r} at={0} x={800 + e.w} size={13} weight={e.bold ? 600 : 400} color={e.col}>
                    {`${e.ms} ms (${e.mult})`}
                  </Line>
                </React.Fragment>
              );
            })}
          </React.Fragment>
        );
      })}

      <Note page={0} x={636} y={rowY(19.8)} at={42} size={23} rotate={-1}>
        979,000 FPS in DOOM · 212M ticks/s in Snake AI!
      </Note>
    </Sheet>
  );
};

/**
 * 4. TokenCostAnim: Animates the 12-Language Token Cost vs Runtime Speed comparison.
 */
export const TokenCostAnim: React.FC = () => {
  const f = useCurrentFrame();
  const rows = data.tokens || [];
  const maxTok = Math.max(...rows.map((r) => r.tokens), 10740);

  return (
    <Sheet pages={1}>
      <Line page={0} row={1.3} at={0} weight={600}>
        TOKEN COST vs. RUNTIME SPEED: ALL 6 KERNELS ACROSS 12 LANGUAGES
      </Line>
      <Line page={0} row={2.2} at={0} color={T.soft} size={17}>
        1-shot LLM API cost ($3/1M in, $15/1M out) vs. warm runtime across all 6 benchmarks
      </Line>

      {/* Column Headers */}
      <Line page={0} row={3.5} at={0} x={84} weight={600} size={15.5} color={T.soft}>
        {"LANGUAGE      LOC    CODE TOKENS (6 KERNELS)          1-SHOT API   WARM RUNTIME (LOWER = FASTER)"}
      </Line>

      {rows.map((r, idx) => {
        const rowNum = 4.6 + idx * 1.22;
        const grow = interpolate(f, [idx * 3, idx * 3 + 24], [0.25, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
        const tokW = Math.max(6, Math.round((r.tokens / maxTok) * 210 * grow));
        const logRatio = Math.log10(Math.max(1, r.geomean)) / Math.log10(600);
        const runW = Math.max(8, Math.round((12 + logRatio * 185) * grow));
        const isAsm = r.id === "asm";
        const col = isAsm ? T.pen : T.ink;

        return (
          <React.Fragment key={r.id}>
            <Line page={0} row={rowNum} at={0} x={84} size={15.5} weight={isAsm ? 600 : 400} color={col}>
              {`${r.name.padEnd(12)} ${String(r.loc).padStart(4)}`}
            </Line>
            <div
              style={{
                position: "absolute",
                left: 295,
                top: rowNum * T.LINE + 7,
                width: tokW,
                height: 14,
                background: isAsm ? T.pen : T.gray,
                borderRadius: 3,
              }}
            />
            <Line page={0} row={rowNum} at={0} x={303 + tokW} size={14.5} weight={isAsm ? 600 : 400} color={col}>
              {`${r.tokens.toLocaleString()} tok`}
            </Line>

            <Line page={0} row={rowNum} at={0} x={630} size={15.5} weight={isAsm ? 600 : 400} color={col}>
              {`$${r.oneshot_usd.toFixed(3)}`}
            </Line>

            <div
              style={{
                position: "absolute",
                left: 745,
                top: rowNum * T.LINE + 7,
                width: runW,
                height: 14,
                background: isAsm ? T.pen : r.geomean > 50 ? T.red : T.ink,
                borderRadius: 3,
              }}
            />
            <Line page={0} row={rowNum} at={0} x={753 + runW} size={14.5} weight={isAsm ? 600 : 400} color={col}>
              {`${r.total_ms.toFixed(1)} ms (${r.geomean.toFixed(1)}x)`}
            </Line>
          </React.Fragment>
        );
      })}

      {/* Reviewer annotations */}
      <Stroke page={0} at={48} d={loopPath(622, rowY(4.6) - 12, 82, 26)} />
      <Note page={0} x={84} y={rowY(20.0)} at={56} size={27} rotate={-1}>
        +$0.13 in tokens once ($0.172 vs $0.039) -&gt; 14.2x to 582.6x faster on every call!
      </Note>
      <Note page={0} x={480} y={rowY(21.3)} at={72} size={22} color={T.soft} rotate={-0.8}>
        Full multi-round verified agent run across all 6 tasks: $14.52 total
      </Note>
    </Sheet>
  );
};

/**
 * 5. GatesAnim: Animates the 5-Gate Verification Pipeline catching subtle LLM
 *    assembly bugs (like test case #11499 at byte 16,177) before installing.
 */
export const GatesAnim: React.FC = () => {
  const f = useCurrentFrame();

  const stages = [
    {
      num: "GATE 1",
      name: "Static Source & Disassembly Lint",
      check: "Rejects svc/brk/hlt, .data/.bss, x18 platform reg, and stack shifts",
      atA: 6,
      atB: 54,
    },
    {
      num: "GATE 2",
      name: "Object Symbol Hygiene (nm)",
      check: "Must export only the target symbol; 0 undefined external calls",
      atA: 14,
      atB: 62,
    },
    {
      num: "GATE 3",
      name: "Custom ABI Canary Trampoline",
      check: "Seeds x19-x29, d8-d15, sp & 128B red zone before call and checks after",
      atA: 22,
      atB: 70,
    },
    {
      num: "GATE 4",
      name: "Page-Table PROT_NONE Guard Pages",
      check: "Places buffers at exact end of page before unmapped page (1B overread = SIGSEGV)",
      atA: 30,
      atB: 78,
    },
    {
      num: "GATE 5",
      name: "Multi-Seed Hold-Out Fuzzing vs ref.c",
      check: "266,383 inputs: empty, 1B, page-boundary, adversarial & fresh PRNG seeds",
      atA: 38,
      atB: 86,
    },
  ];

  return (
    <Sheet pages={1}>
      <Line page={0} row={1.4} at={0} weight={600}>
        HOW VIBEASM VERIFIES ASSEMBLY: 5 GATES BEFORE ANY .s FILE IS TRUSTED
      </Line>
      <Line page={0} row={2.3} at={0} color={T.soft} size={17.5}>
        LLMs write fast SIMD assembly — and make subtle lane-overflow &amp; ABI bugs. Every gate is mandatory.
      </Line>

      <Line page={0} row={3.8} at={0} x={84} weight={600} size={16} color={T.soft}>
        {"VERIFICATION GATE                                      ROUND 1 (v3_tbl3.s)     ROUND 2 (wordcount.s)"}
      </Line>

      {stages.map((st, idx) => {
        const r = 5.2 + idx * 2.4;
        const failA = idx === 4 && f >= st.atA;
        const passA = idx < 4 && f >= st.atA;
        const passB = f >= st.atB;

        return (
          <React.Fragment key={st.num}>
            <Line page={0} row={r} at={0} x={84} weight={600} size={16.5}>
              {`${st.num}: ${st.name}`}
            </Line>
            <Line page={0} row={r + 0.85} at={0} x={84} size={14} color={T.soft}>
              {st.check}
            </Line>

            {passA && (
              <Line page={0} row={r + 0.3} at={st.atA} x={685} weight={600} size={16} color={T.ink}>
                [PASS]
              </Line>
            )}
            {failA && (
              <Line page={0} row={r + 0.3} at={st.atA} x={665} weight={600} size={16} color={T.red}>
                [REJECT #11499]
              </Line>
            )}

            {passB && (
              <Line page={0} row={r + 0.3} at={st.atB} x={945} weight={600} size={16} color={T.pen}>
                [PASS · 20.55x]
              </Line>
            )}
          </React.Fragment>
        );
      })}

      <Stroke page={0} at={42} color={T.red} d={loopPath(658, rowY(15.1) - 14, 175, 30)} />
      <Note page={0} x={84} y={rowY(17.8)} at={46} size={25} color={T.red} rotate={-1}>
        Caught in Round 1: 8-bit lane counter overflowed 255 before uaddlv at byte 16,177!
      </Note>
      <Note page={0} x={84} y={rowY(19.6)} at={92} size={26} color={T.pen} rotate={-1}>
        Round 2 splits inner loop into 8-iter chunks -&gt; 266,383 hold-out cases PASS (20.55x vs C)
      </Note>
    </Sheet>
  );
};

/**
 * 6. AgentWorkflowAnim: Animates how to use vibe-assembly in Claude Code,
 *    OpenAI Codex CLI, Cursor/Windsurf, or any custom CLI agent.
 */
export const AgentWorkflowAnim: React.FC = () => {
  const f = useCurrentFrame();

  const cards = [
    {
      title: "CLAUDE CODE (Skill + Headless Runner)",
      skill: ".claude/skills/vibe-assembly/SKILL.md",
      cmd1: "$ bin/vibeasm run crc32 --agent claude --rounds 3",
      cmd2: 'claude> "Use vibe-assembly to beat clang -O3 on crc32"',
      y: 126,
    },
    {
      title: "OPENAI CODEX CLI (AGENTS.md + --agent codex)",
      skill: ".codex/skills/vibe-assembly/SKILL.md + AGENTS.md",
      cmd1: "$ bin/vibeasm run crc32 --agent codex --model o3",
      cmd2: 'codex> "Run vibeasm work crc32 and optimize solution.s"',
      y: 288,
    },
    {
      title: "CURSOR / WINDSURF / AIDER / ANY LLM",
      skill: ".cursor/rules/vibe-assembly.mdc + --agent cmd",
      cmd1: '$ bin/vibeasm run crc32 --agent cmd --agent-cmd "llm"',
      cmd2: "$ bin/vibeasm brief crc32 | pbcopy   # paste into any chat",
      y: 450,
    },
  ];

  const feed = [
    { at: 0, tag: "[PROMPT]", text: "Read TASK.md + ABI.md + baseline.s (clang -O3)", col: T.ink },
    { at: 10, tag: "[AGENT] ", text: "Wrote v1_pmull.s (4-way clmul fold)", col: T.pen },
    { at: 20, tag: "[CHECK] ", text: "$ vibeasm check v1_pmull.s", col: T.ink },
    { at: 28, tag: "[GATE 3]", text: "FAIL: callee-saved d8 clobbered on return", col: T.red },
    { at: 38, tag: "[AGENT] ", text: "Fixed prologue stp d8, d9 -> wrote v2_pmull12.s", col: T.pen },
    { at: 48, tag: "[BENCH] ", text: "$ vibeasm bench v1_pmull.s v2_pmull12.s", col: T.ink },
    { at: 58, tag: "[SPEED] ", text: "PASS · 19.4x -> 88.06x vs clang -O3 (199.8x @ 1M)", col: T.pen },
    { at: 68, tag: "[JUDGE] ", text: "$ vibeasm accept crc32 (fresh hold-out seeds)", col: T.ink },
    { at: 78, tag: "[INSTALLED]", text: "194,820 cases PASS -> solutions/arm64-darwin/crc32.s", col: T.pen },
  ];

  return (
    <Sheet pages={1}>
      <Line page={0} row={1.3} at={0} weight={600}>
        USING VIBE-ASSEMBLY IN CLAUDE CODE, OPENAI CODEX &amp; CURSOR
      </Line>
      <Line page={0} row={2.2} at={0} color={T.soft} size={17.5}>
        Drop-in skills (.claude, .codex, .cursor, AGENTS.md) + headless multi-round agent harness
      </Line>

      {/* Left Column: 3 Agent Setup Cards */}
      {cards.map((c) => (
        <div
          key={c.title}
          style={{
            position: "absolute",
            left: 84,
            top: c.y,
            width: 515,
            height: 142,
            background: "#e8f0e4",
            border: `2px solid ${T.pen}`,
            borderRadius: 6,
            padding: "8px 12px",
            fontFamily: mono,
          }}
        >
          <div style={{ fontSize: 15, fontWeight: 600, color: T.pen }}>{c.title}</div>
          <div style={{ fontSize: 12.5, color: T.soft, marginTop: 3 }}>Auto-loaded: {c.skill}</div>
          <div
            style={{
              marginTop: 8,
              background: "#161b22",
              color: "#7ee787",
              padding: "6px 8px",
              borderRadius: 4,
              fontSize: 12.5,
              lineHeight: 1.45,
              whiteSpace: "pre",
            }}
          >
            {c.cmd1 + "\n" + c.cmd2}
          </div>
        </div>
      ))}

      {/* Right Column: Live Agent Feedback Loop */}
      <Line page={0} row={4.2} at={0} x={625} weight={600} size={17} color={T.pen}>
        WHAT HAPPENS INSIDE THE AGENT LOOP
      </Line>

      {feed.map((item, idx) => {
        if (f < item.at) return null;
        const r = 5.5 + idx * 1.42;
        return (
          <Line
            key={idx}
            page={0}
            row={r}
            at={item.at}
            x={625}
            size={14}
            weight={item.col === T.pen || item.col === T.red ? 600 : 400}
            color={item.col}
          >
            {`${item.tag} ${item.text}`}
          </Line>
        );
      })}

      <Stroke page={0} at={84} d={loopPath(620, rowY(16.8) - 14, 575, 30)} />
      <Note page={0} x={84} y={rowY(20.6)} at={50} size={26} rotate={-0.8}>
        Works with Claude Code, OpenAI Codex CLI, Cursor, Aider, or any custom model!
      </Note>
    </Sheet>
  );
};
