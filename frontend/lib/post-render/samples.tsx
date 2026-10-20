import { readFile } from "node:fs/promises";
import path from "node:path";
import { render } from "takumi-js";
import { HEIGHT, WIDTH } from "./chrome";
import { postRenderer } from "./fonts";
import type { Brand, Family, SlideRole, SlideSpec } from "./spec";

export const SAMPLE_PHOTO_DIR = "components/landing/photos";
const PHOTOS = ["oak-table.jpg", "workshop-hands.jpg", "workshop.jpg"] as const;

export const SAMPLE_BRAND: Brand = {
  name: "Taller Roble",
  colors: {
    primary: "#5B3A29",
    secondary: "#9BA88D",
    accent: "#C8833B",
    background: "#F3EDE2",
    text: "#2B1D14",
  },
};

type SampleSlide = { role: SlideRole; kicker: string | null; headline: string; body: string | null };

export const SAMPLE_SLIDES: SampleSlide[] = [
  { role: "cover", kicker: "Guía", headline: "Cómo elegir tu mesa de comedor", body: "Tres medidas que conviene saber antes de comprar." },
  { role: "content", kicker: "Medida", headline: "Dejá 90 cm alrededor", body: "Es el espacio justo para correr la silla y pasar sin chocar." },
  { role: "content", kicker: "Madera", headline: "Roble macizo, para siempre", body: "Elegimos cada tabla para que la veta se luzca con los años." },
  { role: "content", kicker: "Forma", headline: "Redonda si el living es chico", body: "Sin esquinas, entra más gente y circula mejor." },
  { role: "cta", kicker: null, headline: "¿Armamos la tuya?", body: "Escribinos y la diseñamos a la medida de tu casa." },
];

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

export async function sampleSpec(family: Family, index: number, withLogo: boolean): Promise<SlideSpec> {
  const count = SAMPLE_SLIDES.length;
  const slide = SAMPLE_SLIDES[index - 1];
  if (!slide) throw new RangeError(`sample slide index out of range: ${index}`);
  const photo = PHOTOS[(index - 1) % PHOTOS.length] ?? PHOTOS[0];
  const image = family === "panorama" ? await panoramaSlice(index, count) : await photoUri(photo);
  return {
    family,
    index,
    count,
    ...slide,
    image,
    logo: withLogo ? { src: sampleLogo(), tone: "dark" } : null,
    brand: SAMPLE_BRAND,
  };
}

function sampleLogo(): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120"><circle cx="60" cy="60" r="50" fill="none" stroke="#2B1D14" stroke-width="8"/><path d="M60 26v68M38 52l22-22 22 22M42 74l18-18 18 18" fill="none" stroke="#2B1D14" stroke-width="8" stroke-linecap="round"/></svg>`;
  return `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`;
}
