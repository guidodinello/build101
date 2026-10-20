import { readImageSize } from "./image-size";

export const FAMILIES = ["editorial", "numbers", "panorama"] as const;
export const ROLES = ["cover", "content", "cta"] as const;
export const TONES = ["light", "dark"] as const;
export const MAX_SLIDES = 10;

export type Family = (typeof FAMILIES)[number];
export type SlideRole = (typeof ROLES)[number];
export type Tone = (typeof TONES)[number];

export type BrandColors = {
  primary: string;
  secondary: string;
  accent: string;
  background: string;
  text: string;
};

export type Brand = {
  name: string | null;
  colors: BrandColors;
};

export type Logo = {
  src: string;
  tone: Tone;
};

export type SlideSpec = {
  family: Family;
  index: number;
  count: number;
  role: SlideRole;
  kicker: string | null;
  headline: string;
  body: string | null;
  image: string;
  logo: Logo | null;
  brand: Brand;
};

// A scene is 1080×1350 and its logo at most 600 px (backend `media/images.py`); a worst-case noise
// JPEG is a 1.25 MB data URI and a noise PNG logo 1.8 MB, so 2.5 MB leaves headroom.
export const MAX_DATA_URI_CHARS = 2_500_000;
export const MAX_IMAGE_SIDE = 4096;
const HEADER_BASE64_CHARS = 65_536;

export class SpecError extends Error {}

// The spec is well formed but its image would be too costly to decode (HTTP 422, not 400).
export class ImageRejectedError extends SpecError {
  constructor(
    readonly code: "image_too_large" | "image_unreadable",
    message: string,
  ) {
    super(message);
  }
}

const HEX = /^#[0-9a-fA-F]{6}$/;
const IMAGE_DATA_URI = /^data:image\/(jpeg|png|webp);base64,/;
const COLOR_KEYS = ["primary", "secondary", "accent", "background", "text"] as const;
const LIMITS = { kicker: 40, headline: 120, body: 320, name: 80 };

type Json = Record<string, unknown>;

function isObject(value: unknown): value is Json {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function oneOf<T extends string>(value: unknown, options: readonly T[], field: string): T {
  if (typeof value === "string" && (options as readonly string[]).includes(value)) return value as T;
  throw new SpecError(`${field} must be one of ${options.join(", ")}`);
}

function text(value: unknown, field: string, max: number): string {
  if (typeof value !== "string" || !value.trim()) throw new SpecError(`${field} must be a non-empty string`);
  if (value.length > max) throw new SpecError(`${field} is longer than ${max} characters`);
  return value.trim();
}

function optionalText(value: unknown, field: string, max: number): string | null {
  if (value === null || value === undefined || value === "") return null;
  return text(value, field, max);
}

function integer(value: unknown, field: string, min: number, max: number): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < min || value > max) {
    throw new SpecError(`${field} must be an integer from ${min} to ${max}`);
  }
  return value;
}

function image(value: unknown, field: string): string {
  if (typeof value !== "string" || !IMAGE_DATA_URI.test(value)) {
    throw new SpecError(`${field} must be a base64 JPEG, PNG or WebP data URI`);
  }
  if (value.length > MAX_DATA_URI_CHARS) {
    throw new ImageRejectedError("image_too_large", `${field} is longer than ${MAX_DATA_URI_CHARS} characters`);
  }
  const size = readImageSize(headerBytes(value));
  if (!size) throw new ImageRejectedError("image_unreadable", `${field} has no readable image header`);
  if (size.width > MAX_IMAGE_SIDE || size.height > MAX_IMAGE_SIDE) {
    throw new ImageRejectedError(
      "image_too_large",
      `${field} is ${size.width}×${size.height}, above ${MAX_IMAGE_SIDE} px on a side`,
    );
  }
  return value;
}

// Most headers fit in the first bytes; a JPEG with a large EXIF or ICC block can push its size
// further out, so fall back to the whole (already length-capped) payload.
function headerBytes(dataUri: string): Uint8Array {
  const payload = dataUri.slice(dataUri.indexOf(",") + 1);
  const head = Buffer.from(payload.slice(0, HEADER_BASE64_CHARS), "base64");
  if (payload.length <= HEADER_BASE64_CHARS || readImageSize(head)) return head;
  return Buffer.from(payload, "base64");
}

function colors(value: unknown): BrandColors {
  if (!isObject(value)) throw new SpecError("brand.colors must be an object");
  const parsed = {} as BrandColors;
  for (const key of COLOR_KEYS) {
    const color = value[key];
    if (typeof color !== "string" || !HEX.test(color)) throw new SpecError(`brand.colors.${key} must be #RRGGBB`);
    parsed[key] = color.toUpperCase();
  }
  return parsed;
}

function logo(value: unknown): Logo | null {
  if (value === null || value === undefined) return null;
  if (!isObject(value)) throw new SpecError("logo must be an object or null");
  return { src: image(value.src, "logo.src"), tone: oneOf(value.tone, TONES, "logo.tone") };
}

export function parseSlideSpec(value: unknown): SlideSpec {
  if (!isObject(value)) throw new SpecError("the body must be a JSON object");
  if (!isObject(value.brand)) throw new SpecError("brand must be an object");
  const count = integer(value.count, "count", 1, MAX_SLIDES);
  return {
    family: oneOf(value.family, FAMILIES, "family"),
    index: integer(value.index, "index", 1, count),
    count,
    role: oneOf(value.role, ROLES, "role"),
    kicker: optionalText(value.kicker, "kicker", LIMITS.kicker),
    headline: text(value.headline, "headline", LIMITS.headline),
    body: optionalText(value.body, "body", LIMITS.body),
    image: image(value.image, "image"),
    logo: logo(value.logo),
    brand: {
      name: optionalText(value.brand.name, "brand.name", LIMITS.name),
      colors: colors(value.brand.colors),
    },
  };
}
