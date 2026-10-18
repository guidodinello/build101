import type { BrandColors } from "./spec";

export const INK = "#1C1814";
export const PAPER = "#FBF8F3";
export const WHITE = "#FFFFFF";
const READABLE = 4.5;

type Rgb = [number, number, number];

function rgb(hex: string): Rgb {
  const value = Number.parseInt(hex.slice(1), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

function channel(value: number): number {
  const scaled = value / 255;
  return scaled <= 0.03928 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4;
}

export function luminance(hex: string): number {
  const [r, g, b] = rgb(hex).map(channel);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(first: string, second: string): number {
  const [light, dark] = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (light + 0.05) / (dark + 0.05);
}

export function isDark(hex: string): boolean {
  return luminance(hex) < 0.18;
}

export function alpha(hex: string, opacity: number): string {
  const [r, g, b] = rgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${opacity})`;
}

export function readableOn(background: string, candidates: string[]): string {
  const readable = candidates.find((color) => contrast(color, background) >= READABLE);
  if (readable) return readable;
  return contrast(INK, background) >= contrast(WHITE, background) ? INK : WHITE;
}

export type Palette = {
  paper: string;
  ink: string;
  accent: string;
  block: string;
  onBlock: string;
  accentOnPaper: string;
};

export function palette(colors: BrandColors): Palette {
  const paper = luminance(colors.background) > 0.7 ? colors.background : PAPER;
  const ink = readableOn(paper, [colors.text, colors.primary, INK]);
  const block = [colors.primary, colors.secondary, colors.accent].find((color) => contrast(color, paper) >= 3) ?? INK;
  return {
    paper,
    ink,
    accent: colors.accent,
    block,
    onBlock: readableOn(block, [paper, colors.background, INK]),
    accentOnPaper: contrast(colors.accent, paper) >= 3 ? colors.accent : block,
  };
}
