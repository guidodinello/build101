import { readFile } from "node:fs/promises";
import path from "node:path";
import { render } from "takumi-js";
import { HEIGHT, WIDTH } from "./design";
import { FONT_PAIRS, type FontPair, postRenderer } from "./fonts";
import {
  EMPHASES,
  FOCUSES,
  LAYOUTS,
  SURFACES,
  type Brand,
  type Emphasis,
  type Family,
  type Focus,
  type Layout,
  type SlideRole,
  type SlideSpec,
  type Surface,
} from "./spec";

export const SAMPLE_PHOTO_DIR = "components/landing/photos";
const PHOTOS = ["oak-table.jpg", "workshop-hands.jpg", "workshop.jpg"] as const;

export const SAMPLE_BRANDS = {
  roble: {
    name: "Taller Roble",
    fonts: "serif-classic",
    colors: { primary: "#5B3A29", secondary: "#9BA88D", accent: "#C8833B", background: "#F3EDE2", text: "#2B1D14" },
  },
  lumbre: {
    name: "Casa Lumbre",
    fonts: "soft-serif",
    colors: { primary: "#7A2E1F", secondary: "#E9C46A", accent: "#E76F51", background: "#FAF3E8", text: "#2A1A14" },
  },
  nube: {
    name: "Nube Estudio",
    fonts: "geometric",
    colors: { primary: "#1F2A44", secondary: "#A8B5C9", accent: "#F2A541", background: "#F4F1EC", text: "#121826" },
  },
  mercado: {
    name: "Mercado Verde",
    fonts: "condensed",
    colors: { primary: "#0F3D2E", secondary: "#C9D6B5", accent: "#F25C2B", background: "#F7F5EE", text: "#10221A" },
  },
} as const satisfies Record<string, Brand>;

export type SampleBrand = keyof typeof SAMPLE_BRANDS;

type SampleSlide = { role: SlideRole; kicker: string | null; headline: string; body: string | null; items: string[] };

export const SAMPLE_SLIDES: SampleSlide[] = [
  { role: "cover", kicker: "Guía", headline: "Cómo elegir tu mesa de comedor", body: "Tres medidas que conviene saber antes de comprar.", items: [] },
  { role: "content", kicker: "Medida", headline: "Dejá 90 cm alrededor", body: "Es el espacio justo para correr la silla y pasar sin chocar.", items: [] },
  {
    role: "content",
    kicker: "Madera",
    headline: "Roble macizo, para siempre",
    body: "Elegimos cada tabla para que la veta se luzca con los años.",
    items: ["Secado natural de 12 meses", "Uniones a caja y espiga", "Aceite vegetal, sin barniz"],
  },
  { role: "content", kicker: "Forma", headline: "Redonda si el living es chico", body: "Sin esquinas, entra más gente y circula mejor.", items: [] },
  { role: "cta", kicker: null, headline: "¿Armamos la tuya?", body: "Escribinos y la diseñamos a la medida de tu casa.", items: [] },
];

export type SampleOptions = {
  family: Family;
  index: number;
  brand: SampleBrand;
  fonts: FontPair | undefined;
  layout: string | undefined;
  emphasis: Emphasis | undefined;
  focus: Focus | undefined;
  surface: Surface | undefined;
  logo: boolean;
};

async function photoUri(name: string): Promise<string> {
  const data = await readFile(path.join(process.cwd(), SAMPLE_PHOTO_DIR, name));
  return `data:image/jpeg;base64,${data.toString("base64")}`;
}

async function panoramaSlice(index: number, count: number): Promise<string> {
  const photo = await photoUri(PHOTOS[0]);
  const slice = await render(
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, overflow: "hidden" }}>
      <img
        src={photo}
        alt=""
        style={{ position: "absolute", top: 0, left: -WIDTH * (index - 1), width: WIDTH * count, height: HEIGHT, objectFit: "cover" }}
      />
    </div>,
    { width: WIDTH, height: HEIGHT, format: "jpeg", quality: 90, renderer: await postRenderer() },
  );
  return `data:image/jpeg;base64,${Buffer.from(slice).toString("base64")}`;
}

function pick<T extends string>(value: string | undefined, options: readonly T[]): T | undefined {
  return options.find((option) => option === value);
}

export function sampleOptions(params: URLSearchParams, family: Family, index: number): SampleOptions {
  const brand = (Object.keys(SAMPLE_BRANDS) as SampleBrand[]).find((name) => name === params.get("brand")) ?? "roble";
  return {
    family,
    index,
    brand,
    fonts: pick(params.get("fonts") ?? undefined, FONT_PAIRS),
    layout: params.get("layout") ?? undefined,
    emphasis: pick(params.get("emphasis") ?? undefined, EMPHASES),
    focus: pick(params.get("focus") ?? undefined, FOCUSES),
    surface: pick(params.get("surface") ?? undefined, SURFACES),
    logo: params.get("logo") === "1",
  };
}

export async function sampleSpec(options: SampleOptions): Promise<SlideSpec> {
  const count = SAMPLE_SLIDES.length;
  const slide = SAMPLE_SLIDES[options.index - 1];
  if (!slide) throw new RangeError(`sample slide index out of range: ${options.index}`);
  const photo = PHOTOS[(options.index - 1) % PHOTOS.length] ?? PHOTOS[0];
  const image = options.family === "panorama" ? await panoramaSlice(options.index, count) : await photoUri(photo);
  const brand = SAMPLE_BRANDS[options.brand];
  const layouts: readonly string[] = LAYOUTS[options.family];
  const layout = (layouts.find((name) => name === options.layout) ?? "auto") as Layout;
  return {
    family: options.family,
    index: options.index,
    count,
    ...slide,
    layout,
    emphasis: options.emphasis ?? "standard",
    focus: options.focus ?? "center",
    surface: options.surface ?? "auto",
    image,
    logo: options.logo ? { src: sampleLogo(brand.colors.text), tone: "dark" } : null,
    brand: { ...brand, colors: { ...brand.colors }, fonts: options.fonts ?? brand.fonts },
  };
}

function sampleLogo(color: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120"><circle cx="60" cy="60" r="50" fill="none" stroke="${color}" stroke-width="8"/><path d="M60 26v68M38 52l22-22 22 22M42 74l18-18 18 18" fill="none" stroke="${color}" stroke-width="8" stroke-linecap="round"/></svg>`;
  return `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`;
}
