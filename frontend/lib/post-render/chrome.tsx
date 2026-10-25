import type { CSSProperties } from "react";
import { ArrowRight, Bookmark } from "lucide";
import { INK, PAPER, alpha, isDark, readableOn } from "./color";
import { type Design, HEIGHT, displayStyle, labelStyle, objectPosition, textStyle } from "./design";
import { Icon } from "./icon";
import type { Focus } from "./spec";

export const SWIPE_LABEL = "Deslizá";
export const SAVE_LABEL = "Guardalo para después";

export function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function needsChip(tone: "light" | "dark", surface: string): boolean {
  return tone === "dark" ? isDark(surface) : !isDark(surface);
}

export function BrandMark({ design, surface, height = 56 }: { design: Design; surface: string; height?: number }) {
  const { spec, type } = design;
  if (spec.logo) {
    const chip = needsChip(spec.logo.tone, surface);
    const image = <img src={spec.logo.src} alt="" style={{ height, maxWidth: height * 4, objectFit: "contain" }} />;
    if (!chip) return image;
    return (
      <div
        style={{
          display: "flex",
          padding: `${Math.round(height * 0.22)}px ${Math.round(height * 0.32)}px`,
          borderRadius: Math.round(height * 0.3),
          backgroundColor: spec.logo.tone === "dark" ? PAPER : INK,
        }}
      >
        {image}
      </div>
    );
  }
  if (!spec.brand.name) return null;
  const size = Math.round(height * 0.62);
  return (
    <div
      style={{
        ...displayStyle(type.display, size),
        lineHeight: 1,
        letterSpacing: type.display.uppercase ? size * 0.06 : type.display.tracking * size,
        color: readableOn(surface, [spec.brand.colors.text, PAPER, INK]),
      }}
    >
      {spec.brand.name}
    </div>
  );
}

export function Counter({ design, color }: { design: Design; color: string }) {
  const { index, count } = design.spec;
  return (
    <div style={{ ...textStyle(design.type, 24, 500), lineHeight: 1, letterSpacing: 2, color }}>
      {`${pad(index)} / ${pad(count)}`}
    </div>
  );
}

export function SwipeCue({ design, color, background }: { design: Design; color: string; background?: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 14,
        padding: background ? "18px 30px" : 0,
        borderRadius: 999,
        backgroundColor: background,
        ...textStyle(design.type, 28, 500),
        lineHeight: 1,
        color,
      }}
    >
      {SWIPE_LABEL}
      <Icon node={ArrowRight} size={30} color={color} />
    </div>
  );
}

export function SavePill({ design, color, background }: { design: Design; color: string; background: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "24px 38px",
        borderRadius: 999,
        backgroundColor: background,
        ...textStyle(design.type, 30, 500),
        lineHeight: 1,
        color,
      }}
    >
      <Icon node={Bookmark} size={30} color={color} />
      {SAVE_LABEL}
    </div>
  );
}

export function Label({ design, text, color, size = 22 }: { design: Design; text: string; color: string; size?: number }) {
  return <div style={{ ...labelStyle(design.type, size), color }}>{text}</div>;
}

export function Photo({
  src,
  width,
  height,
  focus,
  style,
}: {
  src: string;
  width: number | string;
  height: number | string;
  focus: Focus;
  style?: CSSProperties;
}) {
  return (
    <img
      src={src}
      alt=""
      style={{ width, height, objectFit: "cover", objectPosition: objectPosition(focus), ...style }}
    />
  );
}

export function Shade({
  color,
  strength,
  edge,
  solid,
  fade,
}: {
  color: string;
  strength: number;
  edge: "top" | "bottom";
  solid: number;
  fade: number;
}) {
  if (strength <= 0) return null;
  const full = alpha(color, strength);
  const clear = alpha(color, 0);
  const top = edge === "bottom" ? Math.max(0, solid - fade) : 0;
  const bottom = edge === "bottom" ? HEIGHT : Math.min(HEIGHT, solid + fade);
  const height = bottom - top;
  const stop = Math.round(((edge === "bottom" ? solid - top : solid) / height) * 100);
  const stops = edge === "bottom" ? `${clear} 0%, ${full} ${stop}%, ${full} 100%` : `${full} 0%, ${full} ${stop}%, ${clear} 100%`;
  return (
    <div style={{ position: "absolute", left: 0, right: 0, top, height, backgroundImage: `linear-gradient(to bottom, ${stops})` }} />
  );
}
