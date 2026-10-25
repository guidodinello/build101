import { BrandMark, Counter, Label, Photo, SavePill, SwipeCue, pad } from "../chrome";
import { alpha } from "../color";
import {
  type Design,
  type Ground,
  type Template,
  HEIGHT,
  MARGIN,
  WIDTH,
  displayStyle,
  fit,
  ground,
  steps,
  textStyle,
} from "../design";
import type { SlideSpec } from "../spec";

const TEXT_WIDTH = WIDTH - MARGIN * 2;

function Footer({ design, surface, swipe = false }: { design: Design; surface: Ground; swipe?: boolean }) {
  return (
    <div
      style={{
        position: "absolute",
        left: MARGIN,
        right: MARGIN,
        bottom: 72,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}
    >
      <BrandMark design={design} surface={surface.background} height={48} />
      {swipe ? <SwipeCue design={design} color={surface.ink} /> : <Counter design={design} color={alpha(surface.ink, 0.6)} />}
    </div>
  );
}

async function windowCover(design: Design) {
  const { spec, type } = design;
  const surface = ground(design, "paper");
  const frame = { width: 600, height: 700 };
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: TEXT_WIDTH,
    maxLines: 3,
    sizes: steps(spec.emphasis === "statement" ? 164 : 144, 72),
  });
  const frameTop = 96;
  const headlineTop = Math.max(frameTop + frame.height + 56, HEIGHT - 72 - 56 - 48 - headline.height);
  const dot = 300;
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: surface.background }}>
      <div
        style={{
          position: "absolute",
          left: WIDTH - MARGIN - frame.width - dot / 2,
          top: frameTop + frame.height - dot / 2 - 40,
          width: dot,
          height: dot,
          borderRadius: dot,
          backgroundColor: surface.accent,
        }}
      />
      <div style={{ position: "absolute", top: frameTop, right: MARGIN, display: "flex", width: frame.width, height: frame.height, overflow: "hidden" }}>
        <Photo src={spec.image} width={frame.width} height={frame.height} focus={spec.focus} />
      </div>
      {spec.kicker ? (
        <div style={{ position: "absolute", top: frameTop + 8, left: MARGIN, display: "flex" }}>
          <Label design={design} text={spec.kicker} color={alpha(surface.ink, 0.7)} />
        </div>
      ) : null}
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
      <Footer design={design} surface={surface} swipe />
    </div>
  );
}

async function typeCover(design: Design) {
  const { spec, type } = design;
  const surface = ground(design, "brand");
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: TEXT_WIDTH,
    maxLines: 5,
    maxHeight: HEIGHT - 168 - 300 - 168 - 48,
    sizes: steps(232, 96, 6),
  });
  const circle = 300;
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: surface.background }}>
      {spec.kicker ? (
        <div style={{ position: "absolute", top: 96, left: MARGIN, display: "flex" }}>
          <Label design={design} text={spec.kicker} color={alpha(surface.ink, 0.8)} />
        </div>
      ) : null}
      <div
        style={{
          position: "absolute",
          top: 168,
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
          right: MARGIN,
          bottom: 168,
          display: "flex",
          width: circle,
          height: circle,
          overflow: "hidden",
          borderRadius: circle,
          border: `8px solid ${surface.accent}`,
        }}
      >
        <Photo src={spec.image} width={circle} height={circle} focus={spec.focus} />
      </div>
      <Footer design={design} surface={surface} swipe />
    </div>
  );
}

async function windowContent(design: Design) {
  const { spec, type } = design;
  const surface = ground(design, "paper");
  const frame = { width: 640, height: 640 };
  const left = spec.index % 2 === 0;
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: TEXT_WIDTH,
    maxLines: 3,
    sizes: steps(spec.emphasis === "statement" ? 112 : 96, 56),
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
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: surface.background }}>
      <div
        style={{
          position: "absolute",
          top: 96,
          left: left ? MARGIN : undefined,
          right: left ? undefined : MARGIN,
          display: "flex",
          width: frame.width,
          height: frame.height,
          overflow: "hidden",
        }}
      >
        <Photo src={spec.image} width={frame.width} height={frame.height} focus={spec.focus} />
      </div>
      <div
        style={{
          position: "absolute",
          top: 96,
          left: left ? MARGIN + frame.width + 48 : MARGIN,
          display: "flex",
          flexDirection: "column",
          gap: 16,
          width: TEXT_WIDTH - frame.width - 48,
        }}
      >
        <div style={{ ...displayStyle(type.display, 96), lineHeight: 0.9, color: surface.accent }}>{pad(spec.index - 1)}</div>
        {spec.kicker ? <Label design={design} text={spec.kicker} color={alpha(surface.ink, 0.65)} /> : null}
      </div>
      <div style={{ position: "absolute", top: 96 + frame.height + 64, left: MARGIN, right: MARGIN, display: "flex", flexDirection: "column", gap: 24 }}>
        <div style={{ ...displayStyle(type.display, headline.size), color: surface.ink, textWrap: "balance" }}>{spec.headline}</div>
        {body ? <div style={{ ...textStyle(type, body.size), color: alpha(surface.ink, surface.muted), maxWidth: 760 }}>{spec.body}</div> : null}
      </div>
      <Footer design={design} surface={surface} />
    </div>
  );
}

async function side(design: Design) {
  const { spec, type } = design;
  const surface = ground(design, "paper");
  const photoWidth = 500;
  const column = WIDTH - photoWidth - MARGIN - 64;
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: column,
    maxLines: 5,
    sizes: steps(92, 48),
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
      <div style={{ position: "absolute", top: 0, right: 0, bottom: 0, display: "flex", width: photoWidth, overflow: "hidden" }}>
        <Photo src={spec.image} width={photoWidth} height={HEIGHT} focus={spec.focus} />
      </div>
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: MARGIN,
          width: column,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          gap: 28,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div style={{ width: 22, height: 22, borderRadius: 22, backgroundColor: surface.accent }} />
          {spec.kicker ? <Label design={design} text={spec.kicker} color={alpha(surface.ink, 0.65)} /> : null}
        </div>
        <div style={{ ...displayStyle(type.display, headline.size), color: surface.ink, textWrap: "balance" }}>{spec.headline}</div>
        {body ? <div style={{ ...textStyle(type, body.size), color: alpha(surface.ink, surface.muted) }}>{spec.body}</div> : null}
      </div>
      <div style={{ position: "absolute", left: MARGIN, bottom: 72, display: "flex", width: column, justifyContent: "space-between", alignItems: "center" }}>
        <BrandMark design={design} surface={surface.background} height={44} />
        <Counter design={design} color={alpha(surface.ink, 0.6)} />
      </div>
    </div>
  );
}

async function cta(design: Design) {
  const { spec, type } = design;
  const surface = ground(design, "paper");
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: TEXT_WIDTH,
    maxLines: 3,
    sizes: steps(132, 64),
  });
  const circle = 440;
  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 44,
        width: WIDTH,
        height: HEIGHT,
        padding: `0 ${MARGIN}px 120px`,
        backgroundColor: surface.background,
      }}
    >
      <div style={{ position: "relative", display: "flex", width: circle, height: circle }}>
        <div style={{ position: "absolute", left: -36, top: 28, width: circle, height: circle, borderRadius: circle, backgroundColor: surface.accent }} />
        <div style={{ position: "absolute", left: 0, top: 0, display: "flex", width: circle, height: circle, overflow: "hidden", borderRadius: circle }}>
          <Photo src={spec.image} width={circle} height={circle} focus={spec.focus} />
        </div>
      </div>
      <div style={{ ...displayStyle(type.display, headline.size), color: surface.ink, textAlign: "center", width: TEXT_WIDTH, justifyContent: "center", textWrap: "balance" }}>
        {spec.headline}
      </div>
      {spec.body ? (
        <div style={{ ...textStyle(type, 34), color: alpha(surface.ink, surface.muted), textAlign: "center", width: 780, justifyContent: "center", marginTop: -16 }}>
          {spec.body}
        </div>
      ) : null}
      <SavePill design={design} color={surface.background} background={surface.ink} />
      <Footer design={design} surface={surface} />
    </div>
  );
}

export function minimalLayout(spec: SlideSpec): string {
  if (spec.role === "cta") return "cta";
  if (spec.role === "cover") return spec.layout === "type" ? "type" : "window";
  return spec.layout === "side" ? "side" : "window-content";
}

const LAYOUTS: Record<string, Template> = {
  window: windowCover,
  type: typeCover,
  "window-content": windowContent,
  side,
  cta,
};

export async function Minimal(design: Design) {
  return (LAYOUTS[design.report.layout] ?? windowContent)(design);
}
