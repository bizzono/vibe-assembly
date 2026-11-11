// The preview is a line-printer listing on green-bar paper that someone has marked
// up with a pen: the machine prints in ink, the human writes in blue and red.
export const T = {
  W: 1280,
  H: 720,
  LINE: 30, // one printed line
  BAND: 60, // one green bar = two lines
  FONT: 21,
  X0: 100, // left edge of the printed column
  paper: "#f3f5ec",
  band: "#d9e8d2",
  ink: "#1e2622",
  soft: "#5c675f",
  rule: "#bccab8",
  pen: "#2a78d6", // the emphasis hue (validated against both paper tones)
  gray: "#727c75", // de-emphasis marks
  red: "#c2362b", // the reviewer's red pencil: rejections only
} as const;

export const FPS = 30;

// frame at which each page starts printing, and the form-feed between pages
export const FEED = 16;
export const PAGE_AT = [0, 96, 426, 636, 906];
export const END = 1020;
