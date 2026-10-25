import type { Renderer } from "@takumi-rs/core";
import { createElement, type CSSProperties, type ReactNode } from "react";
import { measure, render } from "takumi-js";
import { INK, PAPER, contrast, deepest, isDark, luminance, palette, type Palette } from "./color";
import { TYPEFACES, type Face, type Typeface } from "./fonts";
import type { Focus, SlideSpec } from "./spec";

export const WIDTH = 1080;
export const HEIGHT = 1350;
export const MARGIN = 96;

const GRID_WIDTH = 72;
const GRID_HEIGHT = 90;
const BODY_CONTRAST = 4.5;
const LARGE_CONTRAST = 3;
const BUSY_DEVIATION = 0.12;
const MAX_SCRIM = 0.9;

export type Rect = { x: number; y: number; width: number; height: number };

export type FitReport = { slot: string; size: number; lines: number; clamped: boolean };
export type InkReport = { slot: string; ink: string; contrast: number; scrim: number; busy: boolean };
export type RenderReport = {
  family: string;
  role: string;
  layout: string;
  fits: FitReport[];
  ink: InkReport[];
};

export type Scene = {
  luminance: Float32Array;
  lightness: Float32Array;
};

export type Region = { bright: number; dark: number; mean: number; deviation: number };

export type Legibility = {
  ink: string;
  scrim: string;
  alpha: number;
  contrast: number;
};

export type Design = {
  spec: SlideSpec;
  type: Typeface;
  colors: Palette;
  scene: Scene;
  report: RenderReport;
  renderer: Renderer;
};

export async function createDesign(spec: SlideSpec, renderer: Renderer, layout: string): Promise<Design> {
  return {
    spec,
    type: TYPEFACES[spec.brand.fonts],
    colors: palette(spec.brand.colors),
    scene: await analyzeScene(spec.image, spec.focus, renderer),
    report: { family: spec.family, role: spec.role, layout, fits: [], ink: [] },
    renderer,
  };
}

export function displayStyle(face: Face, size: number): CSSProperties {
  return {
    fontFamily: face.family,
    fontWeight: face.weight,
    fontStyle: face.italic ? "italic" : "normal",
    textTransform: face.uppercase ? "uppercase" : "none",
    letterSpacing: face.tracking * size,
    lineHeight: face.leading,
    fontSize: size,
  };
}

export function textStyle(type: Typeface, size: number, weight = 400): CSSProperties {
  return { fontFamily: type.text, fontWeight: weight, fontSize: size, lineHeight: 1.36, letterSpacing: 0, textWrap: "balance" };
}

export function labelStyle(type: Typeface, size = 22): CSSProperties {
  return {
    fontFamily: type.text,
    fontWeight: type.textBold,
    fontSize: size,
    letterSpacing: size * 0.22,
    textTransform: "uppercase",
    lineHeight: 1,
  };
}

type Fit = {
  slot: string;
  text: string;
  style: (size: number) => CSSProperties;
  width: number;
  maxLines: number;
  maxHeight?: number;
  sizes: number[];
};

function lineCount(node: MeasuredLike): { lines: number; widest: number } {
  const tops = new Set<number>();
  let widest = 0;
  const visit = (current: MeasuredLike) => {
    for (const run of current.runs) {
      if (!run.text.trim()) continue;
      tops.add(Math.round(run.y));
      widest = Math.max(widest, run.x + run.width);
    }
    current.children.forEach(visit);
  };
  visit(node);
  return { lines: tops.size, widest };
}

type MeasuredLike = {
  runs: { text: string; x: number; y: number; width: number }[];
  children: MeasuredLike[];
};

export type Fitted = { size: number; lines: number; height: number };

async function measureText(design: Design, request: Fit, size: number) {
  const node = createElement(
    "div",
    { style: { display: "flex", width: request.width, textWrap: "balance", ...request.style(size) } },
    request.text,
  );
  const measured = (await measure(node, { renderer: design.renderer, width: WIDTH, height: HEIGHT * 3 })) as MeasuredLike & {
    height: number;
  };
  return { ...lineCount(measured), height: measured.height };
}

export async function fit(design: Design, request: Fit): Promise<Fitted> {
  const sizes = [...request.sizes].sort((a, b) => b - a);
  let last = { size: sizes[sizes.length - 1] ?? 32, lines: 0, height: 0 };
  for (const size of sizes) {
    const counted = await measureText(design, request, size);
    last = { size, lines: counted.lines, height: counted.height };
    const tallEnough = request.maxHeight === undefined || counted.height <= request.maxHeight;
    if (counted.lines <= request.maxLines && counted.widest <= request.width + 1 && tallEnough) {
      design.report.fits.push({ slot: request.slot, size, lines: counted.lines, clamped: false });
      return last;
    }
  }
  design.report.fits.push({ slot: request.slot, size: last.size, lines: last.lines, clamped: true });
  return last;
}

export function steps(largest: number, smallest: number, step = 4): number[] {
  const sizes: number[] = [];
  for (let size = largest; size >= smallest; size -= step) sizes.push(size);
  return sizes;
}

const FOCUS_POSITION: Record<Focus, string> = {
  center: "50% 50%",
  top: "50% 15%",
  bottom: "50% 85%",
  left: "15% 50%",
  right: "85% 50%",
};

export function objectPosition(focus: Focus): string {
  return FOCUS_POSITION[focus];
}

function channel(value: number): number {
  const scaled = value / 255;
  return scaled <= 0.03928 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4;
}

async function analyzeScene(src: string, focus: Focus, renderer: Renderer): Promise<Scene> {
  const pixels = await render(
    createElement("img", {
      src,
      style: { width: GRID_WIDTH, height: GRID_HEIGHT, objectFit: "cover", objectPosition: objectPosition(focus) },
    }),
    { renderer, width: GRID_WIDTH, height: GRID_HEIGHT, format: "raw" },
  );
  const count = GRID_WIDTH * GRID_HEIGHT;
  const lum = new Float32Array(count);
  const light = new Float32Array(count);
  for (let i = 0; i < count; i += 1) {
    const r = pixels[i * 4] ?? 0;
    const g = pixels[i * 4 + 1] ?? 0;
    const b = pixels[i * 4 + 2] ?? 0;
    const y = 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
    lum[i] = y;
    light[i] = y ** (1 / 2.2);
  }
  return { luminance: lum, lightness: light };
}

const PATCH = 6;

function patchDeviation(scene: Scene, x0: number, x1: number, y0: number, y1: number): number {
  let busiest = 0;
  for (let py = y0; py < y1; py += PATCH) {
    for (let px = x0; px < x1; px += PATCH) {
      let sum = 0;
      let squares = 0;
      let n = 0;
      for (let y = py; y < Math.min(y1, py + PATCH); y += 1) {
        for (let x = px; x < Math.min(x1, px + PATCH); x += 1) {
          const value = scene.lightness[y * GRID_WIDTH + x] ?? 0;
          sum += value;
          squares += value * value;
          n += 1;
        }
      }
      if (n < 4) continue;
      const mean = sum / n;
      busiest = Math.max(busiest, Math.sqrt(Math.max(0, squares / n - mean * mean)));
    }
  }
  return busiest;
}

export function region(scene: Scene, rect: Rect): Region {
  const x0 = Math.max(0, Math.floor((rect.x / WIDTH) * GRID_WIDTH));
  const x1 = Math.min(GRID_WIDTH, Math.ceil(((rect.x + rect.width) / WIDTH) * GRID_WIDTH));
  const y0 = Math.max(0, Math.floor((rect.y / HEIGHT) * GRID_HEIGHT));
  const y1 = Math.min(GRID_HEIGHT, Math.ceil(((rect.y + rect.height) / HEIGHT) * GRID_HEIGHT));
  const values: number[] = [];
  let sum = 0;
  for (let y = y0; y < y1; y += 1) {
    for (let x = x0; x < x1; x += 1) {
      const value = scene.luminance[y * GRID_WIDTH + x] ?? 0;
      values.push(value);
      sum += value;
    }
  }
  if (!values.length) return { bright: 0, dark: 0, mean: 0, deviation: 0 };
  values.sort((a, b) => a - b);
  const n = values.length;
  return {
    bright: values[Math.min(n - 1, Math.floor(n * 0.92))] ?? 0,
    dark: values[Math.floor(n * 0.08)] ?? 0,
    mean: sum / n,
    deviation: patchDeviation(scene, x0, x1, y0, y1),
  };
}

function ratio(first: number, second: number): number {
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}

function scrimFor(worst: number, inkLum: number, scrimLum: number, target: number, light: boolean): number {
  const limit = light ? (inkLum + 0.05) / target - 0.05 : target * (inkLum + 0.05) - 0.05;
  const needed = light ? worst > limit : worst < limit;
  if (!needed) return 0;
  const alpha = (worst - limit) / (worst - scrimLum);
  return Math.min(MAX_SCRIM, Math.max(0, alpha));
}

export function legible(
  design: Design,
  slot: string,
  rect: Rect,
  options: { prefer?: "light" | "dark"; large?: boolean; light?: string; dark?: string; minimum?: number } = {},
): Legibility {
  const area = region(design.scene, rect);
  const target = options.large ? LARGE_CONTRAST : BODY_CONTRAST;
  const lightInk = options.light ?? PAPER;
  const darkInk = options.dark ?? INK;
  const busy = area.deviation > BUSY_DEVIATION;
  const extra = busy ? Math.min(0.3, (area.deviation - BUSY_DEVIATION) * 2.2) : 0;
  const lightAlpha = scrimFor(area.bright, luminance(lightInk), luminance(darkInk), target, true);
  const darkAlpha = scrimFor(area.dark, luminance(darkInk), luminance(lightInk), target, false);
  const useLight = options.prefer ? options.prefer === "light" : lightAlpha <= darkAlpha;
  const base = useLight ? lightAlpha : darkAlpha;
  const alpha = Math.min(MAX_SCRIM, Math.max(options.minimum ?? 0, base + extra));
  const ink = useLight ? lightInk : darkInk;
  const scrim = useLight ? darkInk : lightInk;
  const worst = useLight ? area.bright : area.dark;
  const blended = worst * (1 - alpha) + luminance(scrim) * alpha;
  const contrast = ratio(luminance(ink), blended);
  design.report.ink.push({ slot, ink, contrast: Math.round(contrast * 10) / 10, scrim: Math.round(alpha * 100) / 100, busy });
  return { ink, scrim, alpha, contrast };
}

export function calmest(design: Design, candidates: Record<string, Rect>): string {
  let best = "";
  let bestScore = Number.POSITIVE_INFINITY;
  for (const [name, rect] of Object.entries(candidates)) {
    const area = region(design.scene, rect);
    const score = area.deviation * 4 + Math.abs(area.mean - 0.12) * 0.6;
    if (score < bestScore) {
      best = name;
      bestScore = score;
    }
  }
  return best;
}

export const RENDER_REPORT_HEADER = "x-render-report";

export function reportHeader(report: RenderReport): string {
  return JSON.stringify(report);
}

export type Template = (design: Design) => Promise<ReactNode>;

export type Ground = { background: string; ink: string; muted: number; accent: string; dark: boolean };

export function ground(design: Design, fallback: "paper" | "brand" | "dark"): Ground {
  const { colors, spec } = design;
  const choice = spec.surface === "auto" ? fallback : spec.surface;
  if (choice === "brand") {
    const accent = contrast(colors.accent, colors.block) >= 3 ? colors.accent : colors.onBlock;
    return { background: colors.block, ink: colors.onBlock, muted: 0.82, accent, dark: isDark(colors.block) };
  }
  if (choice === "dark") {
    const base = deepest(spec.brand.colors);
    const background = luminance(base) < 0.05 ? base : INK;
    const accent = contrast(colors.accent, background) >= 3 ? colors.accent : PAPER;
    return { background, ink: PAPER, muted: 0.8, accent, dark: true };
  }
  return { background: colors.paper, ink: colors.ink, muted: 0.74, accent: colors.accentOnPaper, dark: false };
}
