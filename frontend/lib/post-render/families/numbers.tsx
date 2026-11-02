import { ArrowRight } from "lucide";
import { BrandMark, Counter, Label, Photo, SavePill, pad } from "../chrome";
import { alpha } from "../color";
import {
  type Design,
  type Ground,
  type Template,
  HEIGHT,
  MARGIN,
  WIDTH,
  bodyStyle,
  displayStyle,
  fit,
  ground,
  steps,
  textStyle,
} from "../design";
import { Icon } from "../icon";
import type { SlideSpec } from "../spec";

const TEXT_WIDTH = WIDTH - MARGIN * 2;
const BAND = 720;
const NODE = 120;

function SeamNodes({ design, color, y }: { design: Design; color: string; y: number }) {
  const { index, count } = design.spec;
  const node = { position: "absolute", top: y - NODE / 2, width: NODE, height: NODE, borderRadius: NODE, backgroundColor: color } as const;
  return (
    <>
      {index > 1 ? <div style={{ ...node, left: -NODE / 2 }} /> : null}
      {index < count ? <div style={{ ...node, right: -NODE / 2 }} /> : null}
    </>
  );
}

function Numeral({ design, surface, size }: { design: Design; surface: Ground; size: number }) {
  return (
    <div
      style={{
        ...displayStyle(design.type.display, size),
        lineHeight: 0.8,
        letterSpacing: design.type.display.uppercase ? 0 : -size * 0.05,
        color: surface.accent,
      }}
    >
      {pad(design.spec.index - 1)}
    </div>
  );
}

function Footer({ design, surface, inset = MARGIN }: { design: Design; surface: Ground; inset?: number }) {
  return (
    <div
      style={{
        position: "absolute",
        left: inset,
        right: MARGIN,
        bottom: 64,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}
    >
      <BrandMark design={design} surface={surface.background} height={46} />
      <Counter design={design} color={alpha(surface.ink, 0.6)} />
    </div>
  );
}

async function poster(design: Design) {
  const { spec, type } = design;
  const surface = ground(design, "brand");
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: TEXT_WIDTH,
    maxLines: spec.emphasis === "statement" ? 5 : 4,
    sizes: steps(spec.emphasis === "statement" ? 196 : 172, 80),
  });
  const headlineTop = 196;
  const archTop = Math.max(headlineTop + headline.height + 56, 620);
  const arch = { width: 500, height: HEIGHT - archTop };
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: surface.background }}>
      <div
        style={{
          position: "absolute",
          right: MARGIN,
          bottom: 0,
          display: "flex",
          width: arch.width,
          height: arch.height,
          overflow: "hidden",
          borderRadius: `${arch.width / 2}px ${arch.width / 2}px 0 0`,
        }}
      >
        <Photo src={spec.image} width={arch.width} height={arch.height} focus={spec.focus} />
      </div>
      <div
        style={{
          position: "absolute",
          top: 80,
          left: MARGIN,
          right: MARGIN,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        {spec.kicker ? (
          <div style={{ display: "flex", padding: "14px 26px", borderRadius: 999, border: `2px solid ${surface.ink}` }}>
            <Label design={design} text={spec.kicker} color={surface.ink} />
          </div>
        ) : (
          <div />
        )}
        <BrandMark design={design} surface={surface.background} height={56} />
      </div>
      <div
        style={{
          position: "absolute",
          top: headlineTop,
          left: MARGIN,
          width: TEXT_WIDTH,
          ...displayStyle(type.display, headline.size),
          color: surface.ink,
          textWrap: "balance",
        }}
      >
        {spec.headline}
      </div>
      <div
        style={{
          position: "absolute",
          left: MARGIN,
          bottom: MARGIN,
          width: WIDTH - MARGIN * 2 - arch.width - 48,
          display: "flex",
          flexDirection: "column",
          gap: 36,
        }}
      >
        {spec.body ? <div style={{ ...textStyle(type, 32), color: alpha(surface.ink, surface.muted), lineClamp: 5 }}>{spec.body}</div> : null}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 128,
            height: 128,
            borderRadius: 128,
            backgroundColor: surface.accent,
          }}
        >
          <Icon node={ArrowRight} size={56} color={surface.background} strokeWidth={2.25} />
        </div>
      </div>
    </div>
  );
}

async function band(design: Design) {
  const { spec, type } = design;
  const surface = ground(design, "paper");
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: TEXT_WIDTH,
    maxLines: 3,
    sizes: steps(spec.emphasis === "statement" ? 104 : 88, 52),
  });
  const body = spec.body
    ? await fit(design, {
        slot: "body",
        text: spec.body,
        style: (size) => textStyle(type, size),
        width: TEXT_WIDTH,
        maxLines: 2,
        sizes: steps(36, 30, 2),
      })
    : null;
  const textHeight = 210 + 36 + headline.height + (body ? body.height + 20 : 0);
  const bandHeight = Math.min(BAND, HEIGHT - 150 - textHeight - 24);
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: surface.background }}>
      <div style={{ position: "absolute", top: 0, left: 0, display: "flex", width: WIDTH, height: bandHeight, overflow: "hidden" }}>
        <Photo src={spec.image} width={WIDTH} height={bandHeight} focus={spec.focus} />
      </div>
      <div style={{ position: "absolute", top: bandHeight - 3, left: 0, width: WIDTH, height: 6, backgroundColor: surface.accent }} />
      <SeamNodes design={design} color={surface.accent} y={bandHeight} />
      <div
        style={{
          position: "absolute",
          top: bandHeight + 48,
          left: MARGIN,
          right: MARGIN,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
        }}
      >
        <Numeral design={design} surface={surface} size={210} />
        {spec.kicker ? <Label design={design} text={spec.kicker} color={alpha(surface.ink, 0.62)} /> : null}
      </div>
      <div
        style={{
          position: "absolute",
          top: bandHeight + 48 + 210,
          left: MARGIN,
          right: MARGIN,
          display: "flex",
          flexDirection: "column",
          gap: 20,
        }}
      >
        <div style={{ ...displayStyle(type.display, headline.size), color: surface.ink, textWrap: "balance" }}>{spec.headline}</div>
        {body ? <div style={{ ...bodyStyle(type, body), color: alpha(surface.ink, surface.muted) }}>{spec.body}</div> : null}
      </div>
      <Footer design={design} surface={surface} />
    </div>
  );
}

async function split(design: Design) {
  const { spec, type } = design;
  const surface = ground(design, "paper");
  const photoWidth = 480;
  const column = WIDTH - photoWidth - 72 - MARGIN;
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: column,
    maxLines: 5,
    sizes: steps(88, 48),
  });
  const body = spec.body
    ? await fit(design, {
        slot: "body",
        text: spec.body,
        style: (size) => textStyle(type, size),
        width: column,
        maxLines: 6,
        sizes: steps(34, 30, 2),
      })
    : null;
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: surface.background }}>
      <div style={{ position: "absolute", top: 0, left: 0, bottom: 0, display: "flex", width: photoWidth, overflow: "hidden" }}>
        <Photo src={spec.image} width={photoWidth} height={HEIGHT} focus={spec.focus} />
      </div>
      <div style={{ position: "absolute", top: 0, left: photoWidth - 3, bottom: 0, width: 6, backgroundColor: surface.accent }} />
      <div
        style={{
          position: "absolute",
          top: 120,
          left: photoWidth + 72,
          width: column,
          display: "flex",
          flexDirection: "column",
          gap: 28,
        }}
      >
        <Numeral design={design} surface={surface} size={240} />
        {spec.kicker ? <Label design={design} text={spec.kicker} color={alpha(surface.ink, 0.62)} /> : null}
        <div style={{ ...displayStyle(type.display, headline.size), color: surface.ink, textWrap: "balance" }}>{spec.headline}</div>
        {body ? <div style={{ ...bodyStyle(type, body), color: alpha(surface.ink, surface.muted) }}>{spec.body}</div> : null}
      </div>
      <Footer design={design} surface={surface} inset={photoWidth + 72} />
    </div>
  );
}

async function cta(design: Design) {
  const { spec, type } = design;
  const surface = ground(design, "brand");
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: TEXT_WIDTH,
    maxLines: 3,
    sizes: steps(156, 72),
  });
  const body = spec.body
    ? await fit(design, {
        slot: "body",
        text: spec.body,
        style: (size) => textStyle(type, size),
        width: 760,
        maxLines: 3,
        sizes: steps(36, 30, 2),
      })
    : null;
  const circle = 420;
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: surface.background }}>
      <SeamNodes design={design} color={surface.accent} y={HEIGHT / 2} />
      <div style={{ position: "absolute", top: 150, left: MARGIN, right: MARGIN, display: "flex", flexDirection: "column", gap: 36 }}>
        <div style={{ ...displayStyle(type.display, headline.size), color: surface.ink, textWrap: "balance" }}>{spec.headline}</div>
        {body ? (
          <div style={{ ...bodyStyle(type, body), color: alpha(surface.ink, surface.muted), maxWidth: 760 }}>{spec.body}</div>
        ) : null}
        <div style={{ display: "flex" }}>
          <SavePill design={design} color={surface.background} background={surface.ink} />
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          right: MARGIN,
          bottom: 170,
          display: "flex",
          width: circle,
          height: circle,
          overflow: "hidden",
          borderRadius: circle,
          border: `10px solid ${surface.accent}`,
        }}
      >
        <Photo src={spec.image} width={circle} height={circle} focus={spec.focus} />
      </div>
      <Footer design={design} surface={surface} />
    </div>
  );
}

export function numbersLayout(spec: SlideSpec): string {
  if (spec.role === "cover") return "poster";
  if (spec.role === "cta") return "circle";
  return spec.layout === "split" ? "split" : "band";
}

const LAYOUTS: Record<string, Template> = { poster, band, split, circle: cta };

export async function Numbers(design: Design) {
  return (LAYOUTS[design.report.layout] ?? band)(design);
}
