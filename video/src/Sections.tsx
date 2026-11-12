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

const data = raw as typeof raw & {
  tokens: TokenRow[];
  mandelbrot: string[][];
};

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const rowY = (row: number) => row * T.LINE + T.LINE / 2;

export const SECTION_FRAMES = 240;

/**
 * 1. OneShotAnim: Animates the 1-shot assembly workflow (base64_encode)
 *    from C prototype -> NEON vector assembly -> 5 verification gates -> 23.7 GB/s binary.
 */
export const OneShotAnim: React.FC = () => {
  const f = useCurrentFrame();

  const codeLines = [
    { at: 28, text: "// Load & deinterleave 48 B (16x3)", col: T.soft },
    { at: 36, text: "ld3  {v0.16b-v2.16b}, [x0], #48", col: T.pen },
    { at: 44, text: "// Split 24-bit triples -> 6-bit", col: T.soft },
    { at: 52, text: "ushr v3.16b, v0.16b, #2", col: T.ink },
    { at: 60, text: "ushr v4.16b, v1.16b, #4", col: T.ink },
    { at: 68, text: "sli  v4.16b, v0.16b, #4", col: T.ink },
    { at: 76, text: "ushr v5.16b, v2.16b, #6", col: T.ink },
    { at: 84, text: "sli  v5.16b, v1.16b, #2", col: T.ink },
    { at: 92, text: "and  v6.16b, v2.16b, v20.16b", col: T.ink },
    { at: 100, text: "// 64-byte alphabet LUT in 1 cycle", col: T.soft },
    { at: 108, text: "tbl  v3.16b, {v16.16b-v19.16b}, v3.16b", col: T.pen },
    { at: 116, text: "// Interleave & store 64 Base64 chars", col: T.soft },
    { at: 124, text: "st4  {v3.16b-v6.16b}, [x2], #64", col: T.pen },
  ];

  const gates = [
    { at: 132, title: "GATE 1: Static Source Lint", detail: "141 insns · no svc/brk · no .data" },
    { at: 142, title: "GATE 2: Object Symbol Hygiene", detail: "exports _base64_encode · 0 undef" },
    { at: 152, title: "GATE 3: ABI Canary Trampoline", detail: "x19-x29, d8-d15, sp & red zone ok" },
    { at: 162, title: "GATE 4: PROT_NONE Guard Pages", detail: "1B before/after unmapped pages" },
    { at: 172, title: "GATE 5: Hold-Out Fuzzing", detail: "194,840 cases (2 fresh seeds) PASS" },
  ];

  return (
    <Sheet pages={1}>
      <Line page={0} row={1.5} at={2} weight={600}>
        ONE-SHOT ASSEMBLY WALKTHROUGH: C PROTOTYPE TO 23.7 GB/s NEON KERNEL
      </Line>
      <Line page={0} row={2.5} at={6} color={T.soft} size={18}>
        Task: base64_encode   |   Solved in Round 1 (5.6 min)   |   194,840 hold-out test cases
      </Line>

      {/* Left Column: Spec + Command + Speedup Table */}
      <Line page={0} row={4.5} at={10} x={84} weight={600} size={18} color={T.pen}>
        1. THE C CONTRACT
      </Line>
      <Line page={0} row={5.5} at={14} x={84} size={16}>
        {"size_t base64_encode("}
      </Line>
      <Line page={0} row={6.3} at={16} x={84} size={16}>
        {"  const uint8_t *src,"}
      </Line>
      <Line page={0} row={7.1} at={18} x={84} size={16}>
        {"  size_t n, uint8_t *dst);"}
      </Line>

      <Line page={0} row={9.0} at={22} x={84} weight={600} size={18} color={T.pen}>
        2. ONE COMMAND TO SOLVE
      </Line>
      <Line page={0} row={10.0} at={24} x={84} weight={600} size={17}>
        $ vibeasm run base64_encode
      </Line>

      <Line page={0} row={12.0} at={140} x={84} weight={600} size={18} color={T.pen}>
        3. MEASURED SPEEDUP vs C -O3
      </Line>
      <Line page={0} row={13.0} at={146} x={84} size={16}>
        {"24 B   input :  2.97x faster"}
      </Line>
      <Line page={0} row={13.9} at={152} x={84} size={16}>
        {"255 B  input :  5.27x faster"}
      </Line>
      <Line page={0} row={14.8} at={158} x={84} size={16}>
        {"4 KiB  input :  5.75x faster"}
      </Line>
      <Line page={0} row={15.7} at={164} x={84} size={16}>
        {"1 MiB  input :  5.84x (23.7 GB/s)"}
      </Line>
      <Line page={0} row={17.0} at={172} x={84} weight={600} size={18}>
        {"GEOMEAN      :  4.79x vs clang -O3"}
      </Line>

      {/* Center Column: One-Shot NEON Assembly */}
      <Line page={0} row={4.5} at={26} x={430} weight={600} size={18} color={T.pen}>
        WHAT THE LLM WROTE (64 chars/loop, 0 branches)
      </Line>
      {codeLines.map((ln, idx) => (
        <Line key={idx} page={0} row={5.6 + idx * 0.9} at={ln.at} x={430} size={15.5} color={ln.col} weight={ln.col === T.pen ? 600 : 400}>
          {ln.text}
        </Line>
      ))}

      <Line page={0} row={18.0} at={178} x={430} weight={600} size={16}>
        $ clang -O3 app.c solutions/arm64-darwin/*.s -o app
      </Line>

      {/* Right Column: The 5 Verification Gates */}
      <Line page={0} row={4.5} at={128} x={855} weight={600} size={18} color={T.pen}>
        5 GATES BEFORE INSTALL
      </Line>
      {gates.map((g, idx) => {
        if (f < g.at) return null;
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
              background: "#e4efe0",
              border: `2px solid ${T.pen}`,
              borderRadius: 6,
              padding: "6px 10px",
              fontFamily: mono,
            }}
          >
            <div style={{ fontSize: 14.5, fontWeight: 600, color: T.ink }}>[PASS] {g.title}</div>
            <div style={{ fontSize: 13, color: T.soft, marginTop: 2 }}>{g.detail}</div>
          </div>
        );
      })}

      {/* Reviewer annotations */}
      <Stroke page={0} at={184} d={loopPath(80, rowY(17.0) - 12, 315, 28)} />
      <Note page={0} x={84} y={rowY(19.2)} at={192} size={27} rotate={-1.5}>
        Solved in 1 round — drop straight into C, Rust, or Zig!
      </Note>
      <Note page={0} x={855} y={rowY(18.5)} at={204} size={25} rotate={-2}>
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

  // Progress of each language across the 240-frame animation:
  // Assembly (2.17ms) completes in 18 frames (frame 16 -> 34)
  // C (18.98ms, 8.8x) completes in 158 frames (frame 16 -> 174)
  // Python (469ms, 216.6x) only reaches 18% of the fractal by frame 220!
  const asmRows = Math.floor(interpolate(f, [16, 34], [0, rows], clamp));
  const cRows = Math.floor(interpolate(f, [16, 174], [0, rows], clamp));
  const pyRows = Math.floor(interpolate(f, [16, 230], [0, Math.round(rows * 0.18)], clamp));

  const cellW = 7.2;
  const cellH = 8.5;
  const gx0 = 84;
  const gy0 = 152;

  const racers = [
    { name: "ARM64 Assembly (.s)", ms: "2.17 ms", ratio: "1.0x", progress: interpolate(f, [16, 34], [0, 1], clamp), col: T.pen, bold: true },
    { name: "Rust (rustc -O3)", ms: "18.84 ms", ratio: "8.7x", progress: interpolate(f, [16, 172], [0, 1], clamp), col: T.ink, bold: false },
    { name: "C (clang -O3)", ms: "18.98 ms", ratio: "8.8x", progress: interpolate(f, [16, 174], [0, 1], clamp), col: T.ink, bold: false },
    { name: "Node.js (V8 JIT)", ms: "19.30 ms", ratio: "8.9x", progress: interpolate(f, [16, 177], [0, 1], clamp), col: T.ink, bold: false },
    { name: "Python 3.15", ms: "469.0 ms", ratio: "216.6x", progress: interpolate(f, [16, 230], [0, 0.18], clamp), col: T.red, bold: false },
  ];

  return (
    <Sheet pages={1}>
      <Line page={0} row={1.5} at={2} weight={600}>
        PURE-ASSEMBLY APPLICATION: ZERO C FILES, SINGLE-SYSCALL MANDELBROT
      </Line>
      <Line page={0} row={2.5} at={6} color={T.soft} size={18}>
        $ clang examples/standalone_mandelbrot.s -o mandelbrot &amp;&amp; ./mandelbrot
      </Line>

      {/* Left panel: Live 72x48 pixel canvas rendered from examples/standalone_mandelbrot.s */}
      <Line page={0} row={4.1} at={10} x={gx0} weight={600} size={17} color={T.pen}>
        LIVE STDOUT CAPTURE (72x48 24-bit ANSI half-blocks, 0 C runtime)
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
          {/* Scanline markers showing where C and Python are while Assembly is already done */}
          {f >= 16 && cRows < rows && (
            <g>
              <line x1={0} x2={cols * cellW} y1={cRows * cellH} y2={cRows * cellH} stroke="#ffbd2e" strokeWidth={2.5} />
              <rect x={cols * cellW - 148} y={Math.max(2, cRows * cellH - 18)} width={144} height={16} fill="#161b22" opacity={0.9} />
              <text x={cols * cellW - 76} y={Math.max(14, cRows * cellH - 6)} fill="#ffbd2e" fontSize={11} fontFamily={mono} textAnchor="middle">
                C / Rust / JS scanline
              </text>
            </g>
          )}
          {f >= 16 && (
            <g>
              <line x1={0} x2={cols * cellW} y1={pyRows * cellH} y2={pyRows * cellH} stroke="#ff5f56" strokeWidth={2.5} />
              <rect x={6} y={Math.min(rows * cellH - 20, pyRows * cellH + 3)} width={140} height={16} fill="#161b22" opacity={0.9} />
              <text x={76} y={Math.min(rows * cellH - 8, pyRows * cellH + 15)} fill="#ff5f56" fontSize={11} fontFamily={mono} textAnchor="middle">
                Python (216.6x slower)
              </text>
            </g>
          )}
        </svg>
      </div>

      {/* Right panel: Inside the assembly binary + live race bars */}
      <Line page={0} row={4.1} at={12} x={640} weight={600} size={17} color={T.pen}>
        INSIDE standalone_mandelbrot.s
      </Line>
      <Line page={0} row={5.1} at={18} x={640} size={15.5}>
        {"fmov   d2, #0.25"}
      </Line>
      <Line page={0} row={5.95} at={22} x={640} size={15.5}>
        {"fsub   d3, d0, d2          // cr - 0.25"}
      </Line>
      <Line page={0} row={6.8} at={26} x={640} size={15.5}>
        {"fmadd  d5, d3, d3, d4      // cardioid q"}
      </Line>
      <Line page={0} row={7.65} at={30} x={640} size={15.5} color={T.pen} weight={600}>
        {"b.le   Lpoint_in_set       // skip 200-iter!"}
      </Line>
      <Line page={0} row={8.5} at={34} x={640} size={15.5}>
        {"mov    x0, #1              // stdout fd"}
      </Line>
      <Line page={0} row={9.35} at={38} x={640} size={15.5} color={T.pen} weight={600}>
        {"bl     _write              // 1 syscall flush"}
      </Line>

      <Line page={0} row={11.0} at={20} x={640} weight={600} size={17} color={T.pen}>
        512x512 BENCHMARK RACE (sum = 9,985,499)
      </Line>
      {racers.map((r, i) => {
        const ry = 12.1 + i * 1.35;
        const barW = Math.max(6, Math.round(r.progress * 210));
        return (
          <React.Fragment key={r.name}>
            <Line page={0} row={ry} at={20} x={640} size={15} weight={r.bold ? 600 : 400} color={r.col}>
              {r.name.padEnd(21)}
            </Line>
            {f >= 20 && (
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
            )}
            <Line page={0} row={ry} at={20} x={1075} size={14.5} weight={r.bold ? 600 : 400} color={r.col}>
              {`${r.ms} (${r.ratio})`}
            </Line>
          </React.Fragment>
        );
      })}

      {/* Reviewer handwriting */}
      <Note page={0} x={640} y={rowY(19.2)} at={65} size={27} rotate={-1.5}>
        Assembly finishes in 2.17 ms — before Python draws row 1!
      </Note>
      <Note page={0} x={84} y={rowY(19.5)} at={110} size={25} color={T.red} rotate={-1}>
        Zero libc printf overhead: 100% ARM64 instructions + 1 _write syscall
      </Note>
    </Sheet>
  );
};

/**
 * 3. TokenCostAnim: Animates the 12-Language Token Cost vs Runtime Speed comparison.
 */
export const TokenCostAnim: React.FC = () => {
  const f = useCurrentFrame();
  const rows = data.tokens || [];
  const maxTok = Math.max(...rows.map((r) => r.tokens), 10740);

  return (
    <Sheet pages={1}>
      <Line page={0} row={1.3} at={2} weight={600}>
        TOKEN COST vs. RUNTIME SPEED: ALL 6 KERNELS ACROSS 12 LANGUAGES
      </Line>
      <Line page={0} row={2.2} at={6} color={T.soft} size={17}>
        1-shot LLM API cost ($3/1M in, $15/1M out) vs. warm runtime across all 6 benchmarks
      </Line>

      {/* Column Headers */}
      <Line page={0} row={3.5} at={10} x={84} weight={600} size={15.5} color={T.soft}>
        {"LANGUAGE      LOC    CODE TOKENS (6 KERNELS)          1-SHOT API   WARM RUNTIME (LOWER = FASTER)"}
      </Line>

      {rows.map((r, idx) => {
        const rowNum = 4.6 + idx * 1.22;
        const appearAt = 14 + idx * 6;
        if (f < appearAt) return null;

        const grow = interpolate(f, [appearAt, appearAt + 28], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
        const tokW = Math.max(6, Math.round((r.tokens / maxTok) * 210 * grow));
        const logRatio = Math.log10(Math.max(1, r.geomean)) / Math.log10(600);
        const runW = Math.max(8, Math.round((12 + logRatio * 185) * grow));
        const isAsm = r.id === "asm";
        const col = isAsm ? T.pen : T.ink;

        return (
          <React.Fragment key={r.id}>
            <Line page={0} row={rowNum} at={appearAt} x={84} size={15.5} weight={isAsm ? 600 : 400} color={col}>
              {`${r.name.padEnd(12)} ${String(r.loc).padStart(4)}`}
            </Line>
            {/* Code Token Bar */}
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
            <Line page={0} row={rowNum} at={appearAt} x={303 + tokW} size={14.5} weight={isAsm ? 600 : 400} color={col}>
              {`${r.tokens.toLocaleString()} tok`}
            </Line>

            {/* 1-Shot USD */}
            <Line page={0} row={rowNum} at={appearAt} x={630} size={15.5} weight={isAsm ? 600 : 400} color={col}>
              {`$${r.oneshot_usd.toFixed(3)}`}
            </Line>

            {/* Warm Runtime Bar */}
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
            <Line page={0} row={rowNum} at={appearAt} x={753 + runW} size={14.5} weight={isAsm ? 600 : 400} color={col}>
              {`${r.total_ms.toFixed(1)} ms (${r.geomean.toFixed(1)}x)`}
            </Line>
          </React.Fragment>
        );
      })}

      {/* Reviewer annotations */}
      <Stroke page={0} at={120} d={loopPath(622, rowY(4.6) - 12, 82, 26)} />
      <Note page={0} x={84} y={rowY(20.0)} at={136} size={28} rotate={-1}>
        +$0.13 in tokens once ($0.172 vs $0.039) -&gt; 14.2x to 582.6x faster on every call!
      </Note>
      <Note page={0} x={745} y={rowY(21.2)} at={168} size={22} color={T.soft} rotate={-1}>
        Full multi-round verified agent run across all 6 tasks: $14.52 total
      </Note>
    </Sheet>
  );
};

/**
 * 4. GatesAnim: Animates the 5-Gate Verification Pipeline catching subtle LLM
 *    assembly bugs (like test case #11499 at byte 16,177) before installing.
 */
export const GatesAnim: React.FC = () => {
  const f = useCurrentFrame();

  const stages = [
    {
      num: "GATE 1",
      name: "Static Source & Disassembly Lint",
      check: "Rejects svc/brk/hlt, .data/.bss, x18 platform reg, and stack shifts",
      atA: 20,
      atB: 130,
    },
    {
      num: "GATE 2",
      name: "Object Symbol Hygiene (nm)",
      check: "Must export only the target symbol; 0 undefined external calls",
      atA: 34,
      atB: 142,
    },
    {
      num: "GATE 3",
      name: "Custom ABI Canary Trampoline",
      check: "Seeds x19-x29, d8-d15, sp & 128B red zone before call and checks after",
      atA: 48,
      atB: 154,
    },
    {
      num: "GATE 4",
      name: "Page-Table PROT_NONE Guard Pages",
      check: "Places buffers at exact end of page before unmapped page (1B overread = SIGSEGV)",
      atA: 62,
      atB: 166,
    },
    {
      num: "GATE 5",
      name: "Multi-Seed Hold-Out Fuzzing vs ref.c",
      check: "266,383 inputs: empty, 1B, page-boundary, adversarial & fresh PRNG seeds",
      atA: 76,
      atB: 178,
    },
  ];

  return (
    <Sheet pages={1}>
      <Line page={0} row={1.4} at={2} weight={600}>
        HOW VIBEASM VERIFIES ASSEMBLY: 5 GATES BEFORE ANY .s FILE IS TRUSTED
      </Line>
      <Line page={0} row={2.3} at={6} color={T.soft} size={17.5}>
        LLMs write fast SIMD assembly — and make subtle lane-overflow &amp; ABI bugs. Every gate is mandatory.
      </Line>

      {/* Column headers */}
      <Line page={0} row={3.8} at={12} x={84} weight={600} size={16} color={T.soft}>
        {"VERIFICATION GATE                                      ROUND 1 (v3_tbl3.s)     ROUND 2 (wordcount.s)"}
      </Line>

      {stages.map((st, idx) => {
        const r = 5.2 + idx * 2.4;
        const failA = idx === 4 && f >= st.atA;
        const passA = idx < 4 && f >= st.atA;
        const passB = f >= st.atB;

        return (
          <React.Fragment key={st.num}>
            <Line page={0} row={r} at={14} x={84} weight={600} size={16.5}>
              {`${st.num}: ${st.name}`}
            </Line>
            <Line page={0} row={r + 0.85} at={14} x={84} size={14} color={T.soft}>
              {st.check}
            </Line>

            {/* Candidate A status */}
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

            {/* Candidate B status */}
            {passB && (
              <Line page={0} row={r + 0.3} at={st.atB} x={945} weight={600} size={16} color={T.pen}>
                [PASS · 20.55x]
              </Line>
            )}
          </React.Fragment>
        );
      })}

      {/* Explain the #11499 catch and Round 2 fix */}
      <Stroke page={0} at={86} color={T.red} d={loopPath(658, rowY(15.1) - 14, 175, 30)} />
      <Note page={0} x={84} y={rowY(17.8)} at={92} size={25} color={T.red} rotate={-1}>
        Caught in Round 1: 8-bit lane counter overflowed 255 before uaddlv at byte 16,177!
      </Note>
      <Note page={0} x={84} y={rowY(19.6)} at={188} size={26} color={T.pen} rotate={-1}>
        Round 2 splits inner loop into 8-iter chunks -&gt; 266,383 hold-out cases PASS (20.55x vs C)
      </Note>
    </Sheet>
  );
};
