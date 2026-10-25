import { BrandMark, Photo, SavePill } from "../chrome";
import { INK, PAPER, WHITE, alpha, isDark, mix } from "../color";
import { type Design, type Template, HEIGHT, MARGIN, WIDTH, displayStyle, fit, steps, textStyle } from "../design";
import { HAND } from "../fonts";
import type { SlideSpec } from "../spec";

const TEXT_WIDTH = WIDTH - MARGIN * 2;

type Paper = { base: string; ink: string; muted: string; accent: string; line: string };

function paper(design: Design): Paper {
  const { colors } = design;
  const base = mix(colors.paper, "#F4ECDC", 0.35);
  return { base, ink: colors.ink, muted: alpha(colors.ink, 0.74), accent: colors.accentOnPaper, line: alpha(colors.ink, 0.07) };
}

function Sheet({ tone }: { tone: Paper }) {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        backgroundColor: tone.base,
        backgroundImage: `repeating-linear-gradient(0deg, transparent 0px, transparent 62px, ${tone.line} 62px, ${tone.line} 64px)`,
      }}
    />
  );
}

function Tape({ x, y, angle, color }: { x: number; y: number; angle: number; color: string }) {
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: 190,
        height: 56,
        backgroundColor: alpha(color, 0.55),
        transform: `rotate(${angle}deg)`,
        boxShadow: "0 2px 6px rgba(0, 0, 0, 0.08)",
      }}
    />
  );
}

function arrow(color: string, flip: boolean): string {
  const path = flip
    ? "M200 20 C 150 10, 70 30, 40 110 M40 110 L28 78 M40 110 L72 98"
    : "M20 20 C 70 10, 150 30, 180 110 M180 110 L192 78 M180 110 L148 98";
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="220" height="130" viewBox="0 0 220 130"><path d="${path}" fill="none" stroke="${color}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  return `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`;
}

function swipeArrow(color: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="48" viewBox="0 0 96 48"><path d="M6 30 C 30 18, 56 34, 84 22 M84 22 L66 12 M84 22 L72 38" fill="none" stroke="${color}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  return `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`;
}

function Note({ text, color, x, y, angle, size = 56 }: { text: string; color: string; x: number; y: number; angle: number; size?: number }) {
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        fontFamily: HAND,
        fontWeight: 600,
        fontSize: size,
        lineHeight: 1,
        color,
        transform: `rotate(${angle}deg)`,
      }}
    >
      {text}
    </div>
  );
}

function Polaroid({
  design,
  x,
  y,
  width,
  height,
  angle,
}: {
  design: Design;
  x: number;
  y: number;
  width: number;
  height: number;
  angle: number;
}) {
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        display: "flex",
        padding: "26px 26px 110px",
        backgroundColor: WHITE,
        transform: `rotate(${angle}deg)`,
        boxShadow: "0 22px 50px rgba(40, 28, 16, 0.24)",
      }}
    >
      <Photo src={design.spec.image} width={width} height={height} focus={design.spec.focus} />
    </div>
  );
}

function Footer({ design, tone }: { design: Design; tone: Paper }) {
  return (
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
      <BrandMark design={design} surface={tone.base} height={46} />
      <div style={{ fontFamily: HAND, fontWeight: 600, fontSize: 44, lineHeight: 1, color: tone.muted }}>
        {`${design.spec.index} de ${design.spec.count}`}
      </div>
    </div>
  );
}

async function polaroid(design: Design) {
  const { spec, type } = design;
  const tone = paper(design);
  const cover = spec.role === "cover";
  const flip = spec.index % 2 === 0;
  const photo = cover ? { width: 520, height: 540 } : { width: 500, height: 520 };
  const angle = cover ? -3 : flip ? 2.5 : -2.5;
  const x = flip ? WIDTH - MARGIN - photo.width - 52 - 20 : MARGIN + 20;
  const y = 104;
  const textTop = y + photo.height + 136 + 56;
  const room = HEIGHT - 150 - textTop;
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
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: TEXT_WIDTH,
    maxLines: cover ? 3 : 2,
    maxHeight: room - (body ? body.height + 22 : 0),
    sizes: steps(cover ? 136 : 96, 52),
  });
  const noteX = flip ? MARGIN : x + photo.width + 52 + 28;
  const noteText = spec.kicker ?? (cover ? "¡mirá!" : `#${spec.index - 1}`);
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT }}>
      <Sheet tone={tone} />
      <Polaroid design={design} x={x} y={y} width={photo.width} height={photo.height} angle={angle} />
      <Tape x={x + photo.width / 2 - 70} y={y - 30} angle={flip ? 4 : -5} color={design.colors.accent} />
      <Note text={noteText} color={tone.accent} x={noteX} y={y + 120} angle={flip ? -6 : 6} size={64} />
      <img
        src={arrow(tone.accent, !flip)}
        alt=""
        style={{ position: "absolute", left: flip ? noteX + 40 : noteX - 120, top: y + 210, width: 220, height: 130 }}
      />
      <div style={{ position: "absolute", top: textTop, left: MARGIN, width: TEXT_WIDTH, display: "flex", flexDirection: "column", gap: 22 }}>
        <div style={{ ...displayStyle(type.display, headline.size), color: tone.ink, textWrap: "balance" }}>{spec.headline}</div>
        {body ? <div style={{ ...textStyle(type, body.size), color: tone.muted }}>{spec.body}</div> : null}
      </div>
      {cover ? (
        <div style={{ position: "absolute", right: MARGIN, bottom: 52, display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ fontFamily: HAND, fontWeight: 600, fontSize: 56, lineHeight: 1, color: tone.accent }}>deslizá</div>
          <img src={swipeArrow(tone.accent)} alt="" style={{ width: 96, height: 48 }} />
        </div>
      ) : null}
      {cover ? (
        <div style={{ position: "absolute", left: MARGIN, bottom: 64, display: "flex" }}>
          <BrandMark design={design} surface={tone.base} height={46} />
        </div>
      ) : (
        <Footer design={design} tone={tone} />
      )}
    </div>
  );
}

async function taped(design: Design) {
  const { spec, type } = design;
  const tone = paper(design);
  const photo = { width: TEXT_WIDTH - 40, height: 620 };
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: TEXT_WIDTH,
    maxLines: 2,
    sizes: steps(96, 56),
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
  const x = MARGIN + 20;
  const y = 120;
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT }}>
      <Sheet tone={tone} />
      <div
        style={{
          position: "absolute",
          left: x,
          top: y,
          display: "flex",
          transform: "rotate(-1.2deg)",
          boxShadow: "0 18px 40px rgba(40, 28, 16, 0.22)",
        }}
      >
        <Photo src={spec.image} width={photo.width} height={photo.height} focus={spec.focus} />
      </div>
      <Tape x={x - 60} y={y - 14} angle={-32} color={design.colors.accent} />
      <Tape x={x + photo.width - 130} y={y + photo.height - 40} angle={-32} color={design.colors.accent} />
      {spec.kicker ? <Note text={spec.kicker} color={tone.accent} x={x + photo.width - 260} y={y - 66} angle={-4} size={60} /> : null}
      <div
        style={{
          position: "absolute",
          top: y + photo.height + 80,
          left: MARGIN,
          width: TEXT_WIDTH,
          display: "flex",
          flexDirection: "column",
          gap: 22,
        }}
      >
        <div style={{ ...displayStyle(type.display, headline.size), color: tone.ink, textWrap: "balance" }}>{spec.headline}</div>
        {body ? <div style={{ ...textStyle(type, body.size), color: tone.muted }}>{spec.body}</div> : null}
      </div>
      <Footer design={design} tone={tone} />
    </div>
  );
}

async function cta(design: Design) {
  const { spec, type, colors } = design;
  const tone = paper(design);
  const photo = { width: 400, height: 420 };
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: TEXT_WIDTH,
    maxLines: 3,
    sizes: steps(124, 64),
  });
  const x = (WIDTH - photo.width - 52) / 2;
  const pillInk = isDark(colors.block) ? PAPER : INK;
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT }}>
      <Sheet tone={tone} />
      <Polaroid design={design} x={x} y={96} width={photo.width} height={photo.height} angle={3} />
      <Tape x={x + photo.width / 2 - 70} y={70} angle={-4} color={colors.accent} />
      <div
        style={{
          position: "absolute",
          top: 96 + photo.height + 136 + 56,
          left: MARGIN,
          width: TEXT_WIDTH,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 30,
        }}
      >
        <div style={{ ...displayStyle(type.display, headline.size), color: tone.ink, textAlign: "center", textWrap: "balance", width: TEXT_WIDTH, justifyContent: "center" }}>
          {spec.headline}
        </div>
        {spec.body ? (
          <div style={{ ...textStyle(type, 34), color: tone.muted, textAlign: "center", width: 760, justifyContent: "center" }}>{spec.body}</div>
        ) : null}
        <SavePill design={design} color={pillInk} background={colors.block} />
      </div>
      <Footer design={design} tone={tone} />
    </div>
  );
}

export function scrapbookLayout(spec: SlideSpec): string {
  if (spec.role === "cta") return "cta";
  if (spec.role === "content" && spec.layout === "taped") return "taped";
  return "polaroid";
}

const LAYOUTS: Record<string, Template> = { polaroid, taped, cta };

export async function Scrapbook(design: Design) {
  return (LAYOUTS[design.report.layout] ?? polaroid)(design);
}
