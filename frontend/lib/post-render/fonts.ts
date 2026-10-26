import { readFile } from "node:fs/promises";
import path from "node:path";
import { Renderer } from "@takumi-rs/core";

export const FONT_DIR = "lib/post-render/fonts";

export const FONT_PAIRS = ["serif-classic", "grotesk", "soft-serif", "condensed", "geometric", "friendly-serif"] as const;
export type FontPair = (typeof FONT_PAIRS)[number];
export const DEFAULT_FONT_PAIR: FontPair = "serif-classic";

export const HAND = "Caveat";

export type Face = {
  family: string;
  weight: number;
  italic: boolean;
  uppercase: boolean;
  tracking: number;
  leading: number;
};

export type Typeface = {
  display: Face;
  emphasis: Face;
  text: string;
  textBold: number;
};

const INSTRUMENT = "Instrument Serif";
const BRICOLAGE = "Bricolage Grotesque";
const FRAUNCES = "Fraunces";
const ANTON = "Anton";
const MANROPE = "Manrope";
const YOUNG = "Young Serif";
const DM_SANS = "DM Sans";
const INTER = "Inter";

function face(family: string, weight: number, extra: Partial<Face> = {}): Face {
  return { family, weight, italic: false, uppercase: false, tracking: -0.02, leading: 1, ...extra };
}

export const TYPEFACES: Record<FontPair, Typeface> = {
  "serif-classic": {
    display: face(INSTRUMENT, 400, { tracking: -0.015, leading: 0.98 }),
    emphasis: face(INSTRUMENT, 400, { italic: true, tracking: -0.015, leading: 0.98 }),
    text: DM_SANS,
    textBold: 700,
  },
  grotesk: {
    display: face(BRICOLAGE, 800, { tracking: -0.04, leading: 0.94 }),
    emphasis: face(BRICOLAGE, 500, { tracking: -0.03, leading: 0.98 }),
    text: DM_SANS,
    textBold: 700,
  },
  "soft-serif": {
    display: face(FRAUNCES, 600, { tracking: -0.03, leading: 1 }),
    emphasis: face(FRAUNCES, 600, { italic: true, tracking: -0.03, leading: 1 }),
    text: MANROPE,
    textBold: 700,
  },
  condensed: {
    display: face(ANTON, 400, { uppercase: true, tracking: 0.004, leading: 0.94 }),
    emphasis: face(ANTON, 400, { uppercase: true, tracking: 0.004, leading: 0.94 }),
    text: INTER,
    textBold: 700,
  },
  geometric: {
    display: face(MANROPE, 800, { tracking: -0.05, leading: 0.98 }),
    emphasis: face(MANROPE, 500, { tracking: -0.03, leading: 1.02 }),
    text: MANROPE,
    textBold: 800,
  },
  "friendly-serif": {
    display: face(YOUNG, 400, { tracking: -0.025, leading: 1.04 }),
    emphasis: face(YOUNG, 400, { tracking: -0.025, leading: 1.04 }),
    text: INTER,
    textBold: 700,
  },
};

const FONT_FILES = [
  { name: INSTRUMENT, file: "instrument-serif-latin-400-normal.woff2", weight: 400, style: "normal" },
  { name: INSTRUMENT, file: "instrument-serif-latin-400-italic.woff2", weight: 400, style: "italic" },
  { name: BRICOLAGE, file: "bricolage-grotesque-latin-500-normal.woff2", weight: 500, style: "normal" },
  { name: BRICOLAGE, file: "bricolage-grotesque-latin-800-normal.woff2", weight: 800, style: "normal" },
  { name: FRAUNCES, file: "fraunces-latin-600-normal.woff2", weight: 600, style: "normal" },
  { name: FRAUNCES, file: "fraunces-latin-600-italic.woff2", weight: 600, style: "italic" },
  { name: ANTON, file: "anton-latin-400-normal.woff2", weight: 400, style: "normal" },
  { name: YOUNG, file: "young-serif-latin-400-normal.woff2", weight: 400, style: "normal" },
  { name: HAND, file: "caveat-latin-600-normal.woff2", weight: 600, style: "normal" },
  { name: DM_SANS, file: "dm-sans-latin-400-normal.woff2", weight: 400, style: "normal" },
  { name: DM_SANS, file: "dm-sans-latin-500-normal.woff2", weight: 500, style: "normal" },
  { name: DM_SANS, file: "dm-sans-latin-700-normal.woff2", weight: 700, style: "normal" },
  { name: MANROPE, file: "manrope-latin-400-normal.woff2", weight: 400, style: "normal" },
  { name: MANROPE, file: "manrope-latin-500-normal.woff2", weight: 500, style: "normal" },
  { name: MANROPE, file: "manrope-latin-700-normal.woff2", weight: 700, style: "normal" },
  { name: MANROPE, file: "manrope-latin-800-normal.woff2", weight: 800, style: "normal" },
  { name: INTER, file: "inter-latin-400-normal.woff2", weight: 400, style: "normal" },
  { name: INTER, file: "inter-latin-500-normal.woff2", weight: 500, style: "normal" },
  { name: INTER, file: "inter-latin-700-normal.woff2", weight: 700, style: "normal" },
] as const;

let renderer: Promise<Renderer> | undefined;

async function load(): Promise<Renderer> {
  const instance = new Renderer();
  for (const font of FONT_FILES) {
    const data = await readFile(path.join(process.cwd(), FONT_DIR, font.file));
    await instance.registerFont({ name: font.name, data, weight: font.weight, style: font.style });
  }
  return instance;
}

export function postRenderer(): Promise<Renderer> {
  renderer ??= load().catch((error: unknown) => {
    renderer = undefined;
    throw error;
  });
  return renderer;
}
