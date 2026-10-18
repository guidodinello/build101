import { ArrowRight, Bookmark } from "lucide";
import { INK, PAPER, isDark, readableOn } from "./color";
import { SANS } from "./fonts";
import { Icon } from "./icon";
import type { Brand, Logo } from "./spec";

export const WIDTH = 1080;
export const HEIGHT = 1350;
export const MARGIN = 96;

export const SWIPE_LABEL = "Deslizá";
export const SAVE_LABEL = "Guardalo para después";

export function pad(value: number): string {
  return String(value).padStart(2, "0");
}

export function sizeFor(text: string, steps: [number, number][], smallest: number): number {
  return steps.find(([maxLength]) => text.length <= maxLength)?.[1] ?? smallest;
}

function needsChip(logo: Logo, surface: string): boolean {
  return logo.tone === "dark" ? isDark(surface) : !isDark(surface);
}

export function BrandMark({
  brand,
  logo,
  surface,
  height = 64,
}: {
  brand: Brand;
  logo: Logo | null;
  surface: string;
  height?: number;
}) {
  if (logo) {
    const chip = needsChip(logo, surface);
    const image = (
      <img
        src={logo.src}
        alt=""
        style={{ height, maxWidth: height * 4, objectFit: "contain" }}
      />
    );
    if (!chip) return image;
    return (
      <div
        style={{
          display: "flex",
          padding: `${Math.round(height * 0.22)}px ${Math.round(height * 0.32)}px`,
          borderRadius: Math.round(height * 0.3),
          backgroundColor: logo.tone === "dark" ? PAPER : INK,
        }}
      >
        {image}
      </div>
    );
  }
  if (!brand.name) return null;
  return (
    <div
      style={{
        fontFamily: SANS,
        fontWeight: 700,
        fontSize: 24,
        letterSpacing: 4,
        textTransform: "uppercase",
        color: readableOn(surface, [brand.colors.text, PAPER, INK]),
      }}
    >
      {brand.name}
    </div>
  );
}

export function Counter({ index, count, color }: { index: number; count: number; color: string }) {
  return (
    <div style={{ fontFamily: SANS, fontWeight: 500, fontSize: 24, letterSpacing: 3, color }}>
      {`${pad(index)} / ${pad(count)}`}
    </div>
  );
}

export function SwipeCue({ color, background }: { color: string; background?: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 14,
        padding: background ? "16px 28px" : 0,
        borderRadius: 999,
        backgroundColor: background,
        fontFamily: SANS,
        fontWeight: 500,
        fontSize: 26,
        letterSpacing: 1,
        color,
      }}
    >
      {SWIPE_LABEL}
      <Icon node={ArrowRight} size={30} color={color} />
    </div>
  );
}

export function SavePill({ color, background }: { color: string; background: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "22px 36px",
        borderRadius: 999,
        backgroundColor: background,
        fontFamily: SANS,
        fontWeight: 500,
        fontSize: 28,
        color,
      }}
    >
      <Icon node={Bookmark} size={30} color={color} />
      {SAVE_LABEL}
    </div>
  );
}

export function Kicker({ text, color }: { text: string; color: string }) {
  return (
    <div
      style={{
        fontFamily: SANS,
        fontWeight: 700,
        fontSize: 22,
        letterSpacing: 6,
        textTransform: "uppercase",
        color,
      }}
    >
      {text}
    </div>
  );
}
