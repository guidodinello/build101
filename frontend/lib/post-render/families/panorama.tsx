import { BrandMark, Counter, Label, Photo, SavePill, Shade, SwipeCue } from "../chrome";
import { alpha } from "../color";
import { type Design, HEIGHT, MARGIN, WIDTH, displayStyle, fit, legible, steps, textStyle } from "../design";
import type { SlideSpec } from "../spec";

const TEXT_WIDTH = WIDTH - MARGIN * 2;
const LINE_Y = 250;
const DOT = 64;

export function panoramaLayout(spec: SlideSpec): string {
  return spec.role === "cover" ? "cover" : spec.role === "cta" ? "cta" : "slice";
}

export async function Panorama(design: Design) {
  const { spec, type, colors } = design;
  const cover = spec.role === "cover";
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: TEXT_WIDTH,
    maxLines: cover ? 3 : 2,
    sizes: steps(cover ? 148 : 112, 64),
  });
  const body = spec.body
    ? await fit(design, {
        slot: "body",
        text: spec.body,
        style: (size) => textStyle(type, size),
        width: 820,
        maxLines: 2,
        sizes: steps(38, 32, 2),
      })
    : null;
  const blockTop = LINE_Y + 72;
  const blockHeight = headline.height + (body ? body.height + 24 : 0) + (spec.role === "cta" ? 120 : 0);
  const text = legible(design, "headline", { x: MARGIN, y: LINE_Y - 100, width: TEXT_WIDTH, height: blockTop + blockHeight - LINE_Y + 100 }, {
    large: !body,
    dark: colors.ink,
    minimum: 0.12,
  });
  if (body) {
    const bodyTop = blockTop + headline.height + 24;
    const under = legible(design, "body", { x: MARGIN, y: bodyTop, width: 820, height: body.height }, {
      prefer: text.ink === colors.ink ? "dark" : "light",
      dark: colors.ink,
    });
    text.alpha = Math.max(text.alpha, under.alpha);
  }
  const foot = legible(design, "footer", { x: MARGIN, y: HEIGHT - 150, width: TEXT_WIDTH, height: 90 }, {
    large: true,
    dark: colors.ink,
  });
  const dotCenter = MARGIN + DOT / 2;
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: colors.ink }}>
      <Photo src={spec.image} width={WIDTH} height={HEIGHT} focus="center" style={{ position: "absolute", inset: 0 }} />
      <Shade color={text.scrim} strength={text.alpha} edge="top" solid={blockTop + blockHeight} fade={220} />
      <Shade color={foot.scrim} strength={foot.alpha} edge="bottom" solid={HEIGHT - 150} fade={150} />
      {spec.count > 1 ? (
        <div
          style={{
            position: "absolute",
            top: LINE_Y - 1,
            left: spec.index === 1 ? dotCenter : 0,
            right: spec.index === spec.count ? WIDTH - dotCenter : 0,
            height: 3,
            backgroundColor: alpha(text.ink, 0.85),
          }}
        />
      ) : null}
      <div
        style={{
          position: "absolute",
          top: LINE_Y - DOT / 2,
          left: MARGIN,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: DOT,
          height: DOT,
          borderRadius: DOT,
          backgroundColor: colors.accent,
          ...textStyle(type, 26, type.textBold),
          lineHeight: 1,
          color: colors.paper,
        }}
      >
        {spec.index}
      </div>
      {spec.kicker ? (
        <div style={{ position: "absolute", top: LINE_Y - 96, left: MARGIN, display: "flex" }}>
          <Label design={design} text={spec.kicker} color={text.ink} />
        </div>
      ) : null}
      <div style={{ position: "absolute", top: blockTop, left: MARGIN, right: MARGIN, display: "flex", flexDirection: "column", gap: 24 }}>
        <div style={{ ...displayStyle(type.display, headline.size), color: text.ink, textWrap: "balance" }}>{spec.headline}</div>
        {body ? <div style={{ ...textStyle(type, body.size), color: alpha(text.ink, 0.92), maxWidth: 820 }}>{spec.body}</div> : null}
        {spec.role === "cta" ? (
          <div style={{ display: "flex", marginTop: 16 }}>
            <SavePill design={design} color={text.ink === colors.ink ? colors.paper : colors.ink} background={text.ink} />
          </div>
        ) : null}
      </div>
      <div
        style={{
          position: "absolute",
          left: MARGIN,
          right: MARGIN,
          bottom: 64,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <BrandMark design={design} surface={foot.ink === colors.ink ? colors.paper : colors.ink} height={48} />
        {cover ? <SwipeCue design={design} color={foot.ink} /> : <Counter design={design} color={alpha(foot.ink, 0.85)} />}
      </div>
    </div>
  );
}
