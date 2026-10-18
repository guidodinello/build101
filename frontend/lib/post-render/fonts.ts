import { readFile } from "node:fs/promises";
import path from "node:path";
import { Renderer } from "@takumi-rs/core";

export const SERIF = "Instrument Serif";
export const SANS = "DM Sans";
export const GROTESK = "Bricolage Grotesque";

export const FONT_DIR = "lib/post-render/fonts";

const FONT_FILES = [
  { name: SERIF, file: "instrument-serif-latin-400-normal.woff2", weight: 400, style: "normal" },
  { name: SERIF, file: "instrument-serif-latin-400-italic.woff2", weight: 400, style: "italic" },
  { name: SANS, file: "dm-sans-latin-400-normal.woff2", weight: 400, style: "normal" },
  { name: SANS, file: "dm-sans-latin-500-normal.woff2", weight: 500, style: "normal" },
  { name: SANS, file: "dm-sans-latin-700-normal.woff2", weight: 700, style: "normal" },
  { name: GROTESK, file: "bricolage-grotesque-latin-500-normal.woff2", weight: 500, style: "normal" },
  { name: GROTESK, file: "bricolage-grotesque-latin-800-normal.woff2", weight: 800, style: "normal" },
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
