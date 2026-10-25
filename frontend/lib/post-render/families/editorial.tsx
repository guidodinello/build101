import { BrandMark, Counter, Label, Photo, SavePill, Shade, SwipeCue, pad } from "../chrome";
import { alpha } from "../color";
import {
  type Design,
  type Template,
  HEIGHT,
  MARGIN,
  WIDTH,
  displayStyle,
  fit,
  ground,
  legible,
  steps,
  textStyle,
} from "../design";
import type { SlideSpec } from "../spec";

const TEXT_WIDTH = WIDTH - MARGIN * 2;
const SWIPE_ROW = 66;

async function overlayCover(design: Design) {
  const { spec, type } = design;
  const statement = spec.emphasis === "statement";
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: TEXT_WIDTH,
    maxLines: statement ? 4 : 3,
    sizes: steps(statement ? 176 : 156, 76),
  });
  const body =
    spec.body && !statement
      ? await fit(design, {
          slot: "body",
          text: spec.body,
          style: (size) => textStyle(type, size),
          width: 800,
          maxLines: 2,
          sizes: steps(40, 32, 2),
        })
      : null;
  const blockHeight = 32 + headline.height + (body ? body.height + 28 : 0) + 44 + SWIPE_ROW;
  const top = HEIGHT - MARGIN - blockHeight;
  const ink = legible(design, "headline", { x: MARGIN, y: top, width: TEXT_WIDTH, height: blockHeight }, {
    prefer: "light",
    large: !body,
    dark: design.colors.ink,
    minimum: 0.3,
  });
  const mast = legible(design, "masthead", { x: MARGIN, y: 64, width: TEXT_WIDTH, height: 80 }, {
    large: true,
    dark: design.colors.ink,
  });
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: design.colors.ink }}>
      <Photo src={spec.image} width={WIDTH} height={HEIGHT} focus={spec.focus} style={{ position: "absolute", inset: 0 }} />
      <Shade color={mast.scrim} strength={mast.alpha} from={0} to={260} edge="top" />
      <Shade color={ink.scrim} strength={ink.alpha} from={Math.max(0, top - 300)} to={HEIGHT} edge="bottom" />
      <div
        style={{
          position: "absolute",
          top: 72,
          left: MARGIN,
          right: MARGIN,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <BrandMark design={design} surface={mast.ink === design.colors.ink ? design.colors.paper : design.colors.ink} height={60} />
        {spec.kicker ? <Label design={design} text={spec.kicker} color={mast.ink} /> : null}
      </div>
      <div style={{ position: "absolute", left: MARGIN, right: MARGIN, top, display: "flex", flexDirection: "column" }}>
        <div style={{ width: 96, height: 4, marginBottom: 28, backgroundColor: design.colors.accent }} />
        <div style={{ ...displayStyle(type.display, headline.size), color: ink.ink, textWrap: "balance" }}>{spec.headline}</div>
        {body ? (
          <div style={{ ...textStyle(type, body.size), color: alpha(ink.ink, 0.9), marginTop: 28, maxWidth: 800 }}>{spec.body}</div>
        ) : null}
        <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", marginTop: 44, height: SWIPE_ROW }}>
          <SwipeCue design={design} color={ink.ink === design.colors.ink ? design.colors.paper : design.colors.ink} background={ink.ink} />
        </div>
      </div>
    </div>
  );
}

async function frameCover(design: Design) {
  const { spec, type } = design;
  const surface = ground(design, "paper");
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: TEXT_WIDTH,
    maxLines: 2,
    sizes: steps(132, 64),
  });
  const mastTop = 64;
  const photoTop = 212;
  const bottomRow = HEIGHT - MARGIN - SWIPE_ROW;
  const headlineTop = bottomRow - 40 - headline.height;
  const photoHeight = headlineTop - 44 - photoTop;
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: surface.background }}>
      <div
        style={{
          position: "absolute",
          top: mastTop,
          left: MARGIN,
          right: MARGIN,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          paddingBottom: 24,
          borderBottom: `2px solid ${alpha(surface.ink, 0.85)}`,
        }}
      >
        <BrandMark design={design} surface={surface.background} height={84} />
        {spec.kicker ? <Label design={design} text={spec.kicker} color={surface.ink} /> : null}
      </div>
      <div style={{ position: "absolute", top: photoTop, left: MARGIN, width: TEXT_WIDTH, height: photoHeight, display: "flex", overflow: "hidden" }}>
        <Photo src={spec.image} width="100%" height="100%" focus={spec.focus} />
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
          top: bottomRow,
          left: MARGIN,
          right: MARGIN,
          height: SWIPE_ROW,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ ...textStyle(type, 30), color: alpha(surface.ink, surface.muted), maxWidth: 560, lineClamp: 2 }}>{spec.body ?? ""}</div>
        <SwipeCue design={design} color={surface.background} background={surface.ink} />
      </div>
    </div>
  );
}

async function photoTop(design: Design) {
  const { spec, type } = design;
  const surface = ground(design, "paper");
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
        width: TEXT_WIDTH,
        maxLines: 3,
        sizes: steps(38, 32, 2),
      })
    : null;
  const footer = 72 + 56;
  const textHeight = 64 + 36 + headline.height + (body ? body.height + 24 : 0);
  const photoHeight = Math.min(720, HEIGHT - footer - textHeight - 72);
  return (
    <div style={{ position: "relative", display: "flex", flexDirection: "column", width: WIDTH, height: HEIGHT, backgroundColor: surface.background }}>
      <div style={{ display: "flex", width: WIDTH, height: photoHeight, overflow: "hidden" }}>
        <Photo src={spec.image} width={WIDTH} height={photoHeight} focus={spec.focus} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", padding: `56px ${MARGIN}px 0` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 22, height: 64 }}>
          <div style={{ ...displayStyle(type.emphasis, 60), lineHeight: 1, color: surface.accent }}>{pad(spec.index - 1)}</div>
          <div style={{ flexGrow: 1, height: 2, backgroundColor: alpha(surface.ink, 0.18) }} />
          {spec.kicker ? <Label design={design} text={spec.kicker} color={alpha(surface.ink, 0.72)} /> : null}
        </div>
        <div style={{ ...displayStyle(type.display, headline.size), color: surface.ink, marginTop: 36, textWrap: "balance" }}>
          {spec.headline}
        </div>
        {body ? <div style={{ ...textStyle(type, body.size), color: alpha(surface.ink, surface.muted), marginTop: 24 }}>{spec.body}</div> : null}
      </div>
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
        <Counter design={design} color={alpha(surface.ink, 0.6)} />
      </div>
    </div>
  );
}

async function fullBleed(design: Design) {
  const { spec, type } = design;
  const surface = ground(design, "paper");
  const inner = TEXT_WIDTH - 112;
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: inner,
    maxLines: 3,
    sizes: steps(88, 52),
  });
  const body = spec.body
    ? await fit(design, {
        slot: "body",
        text: spec.body,
        style: (size) => textStyle(type, size),
        width: inner,
        maxLines: 3,
        sizes: steps(36, 30, 2),
      })
    : null;
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: design.colors.ink }}>
      <Photo src={spec.image} width={WIDTH} height={HEIGHT} focus={spec.focus} style={{ position: "absolute", inset: 0 }} />
      <div
        style={{
          position: "absolute",
          left: MARGIN - 40,
          right: MARGIN - 40,
          bottom: MARGIN - 40,
          display: "flex",
          flexDirection: "column",
          padding: "52px 56px 44px",
          backgroundColor: surface.background,
          boxShadow: "0 24px 60px rgba(0, 0, 0, 0.25)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div style={{ ...displayStyle(type.emphasis, 44), lineHeight: 1, color: surface.accent }}>{pad(spec.index - 1)}</div>
          {spec.kicker ? <Label design={design} text={spec.kicker} color={alpha(surface.ink, 0.7)} /> : null}
        </div>
        <div style={{ ...displayStyle(type.display, headline.size), color: surface.ink, marginTop: 26, textWrap: "balance" }}>
          {spec.headline}
        </div>
        {body ? <div style={{ ...textStyle(type, body.size), color: alpha(surface.ink, surface.muted), marginTop: 20 }}>{spec.body}</div> : null}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginTop: 40,
            paddingTop: 28,
            borderTop: `2px solid ${alpha(surface.ink, 0.12)}`,
          }}
        >
          <BrandMark design={design} surface={surface.background} height={44} />
          <Counter design={design} color={alpha(surface.ink, 0.6)} />
        </div>
      </div>
    </div>
  );
}

async function quote(design: Design) {
  const { spec, type } = design;
  const surface = ground(design, "paper");
  const statement = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: TEXT_WIDTH,
    maxLines: 4,
    sizes: steps(spec.emphasis === "statement" ? 184 : 164, 72),
  });
  const thumb = { width: 300, height: 375 };
  const zoneTop = 200;
  const zoneBottom = HEIGHT - 168 - thumb.height - 40;
  const statementTop = zoneTop + Math.max(0, (zoneBottom - zoneTop - statement.height) / 2);
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: surface.background }}>
      <div style={{ position: "absolute", top: 88, left: MARGIN, right: MARGIN, display: "flex", alignItems: "center", gap: 22 }}>
        <div style={{ ...displayStyle(type.emphasis, 60), lineHeight: 1, color: surface.accent }}>{pad(spec.index - 1)}</div>
        <div style={{ flexGrow: 1, height: 2, backgroundColor: alpha(surface.ink, 0.18) }} />
        {spec.kicker ? <Label design={design} text={spec.kicker} color={alpha(surface.ink, 0.72)} /> : null}
      </div>
      <div
        style={{
          position: "absolute",
          top: statementTop,
          left: MARGIN,
          width: TEXT_WIDTH,
          ...displayStyle(type.display, statement.size),
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
          right: MARGIN,
          bottom: 168,
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          gap: 48,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 520 }}>
          <div style={{ width: 72, height: 4, backgroundColor: surface.accent }} />
          {spec.body ? <div style={{ ...textStyle(type, 34), color: alpha(surface.ink, surface.muted), lineClamp: 5 }}>{spec.body}</div> : null}
        </div>
        <div style={{ display: "flex", width: thumb.width, height: thumb.height, overflow: "hidden", flexShrink: 0 }}>
          <Photo src={spec.image} width={thumb.width} height={thumb.height} focus={spec.focus} />
        </div>
      </div>
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
        <Counter design={design} color={alpha(surface.ink, 0.6)} />
      </div>
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
    sizes: steps(128, 64),
  });
  const body = spec.body
    ? await fit(design, {
        slot: "body",
        text: spec.body,
        style: (size) => textStyle(type, size),
        width: 780,
        maxLines: 2,
        sizes: steps(36, 30, 2),
      })
    : null;
  const arch = { width: 400, height: 500 };
  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        width: WIDTH,
        height: HEIGHT,
        padding: `84px ${MARGIN}px 72px`,
        backgroundColor: surface.background,
      }}
    >
      <BrandMark design={design} surface={surface.background} height={64} />
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", flexGrow: 1, gap: 40 }}>
        <div
          style={{
            display: "flex",
            width: arch.width,
            height: arch.height,
            overflow: "hidden",
            borderRadius: `${arch.width / 2}px ${arch.width / 2}px 8px 8px`,
          }}
        >
          <Photo src={spec.image} width={arch.width} height={arch.height} focus={spec.focus} />
        </div>
        <div style={{ ...displayStyle(type.display, headline.size), textAlign: "center", color: surface.ink, textWrap: "balance", width: TEXT_WIDTH, justifyContent: "center" }}>
          {spec.headline}
        </div>
        {body ? (
          <div style={{ ...textStyle(type, body.size), textAlign: "center", color: alpha(surface.ink, surface.muted), width: 780, justifyContent: "center", marginTop: -12 }}>
            {spec.body}
          </div>
        ) : null}
        <SavePill design={design} color={surface.background} background={surface.ink} />
      </div>
      <Counter design={design} color={alpha(surface.ink, 0.7)} />
    </div>
  );
}

export function editorialLayout(spec: SlideSpec): string {
  const { role, layout } = spec;
  if (role === "cta") return "card";
  if (role === "cover") return layout === "frame" ? "frame" : "overlay";
  if (layout === "full-bleed" || layout === "quote") return layout;
  return "photo-top";
}

const LAYOUTS: Record<string, Template> = {
  overlay: overlayCover,
  frame: frameCover,
  "photo-top": photoTop,
  "full-bleed": fullBleed,
  quote,
  card: cta,
};

export async function Editorial(design: Design) {
  const chosen = LAYOUTS[design.report.layout] ?? photoTop;
  return chosen(design);
}
