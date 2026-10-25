import { Check } from "lucide";
import { BrandMark, Photo, SavePill, SwipeCue, pad } from "../chrome";
import { INK, PAPER, WHITE, alpha, isDark, mix } from "../color";
import { type Design, bodyStyle, type Template, HEIGHT, WIDTH, displayStyle, fit, steps, textStyle } from "../design";
import { Icon } from "../icon";
import type { SlideSpec } from "../spec";

const CARD_X = 72;
const CARD_WIDTH = WIDTH - CARD_X * 2;
const PADDING = 64;
const INNER = CARD_WIDTH - PADDING * 2;

type Card = { background: string; ink: string; muted: string; accent: string; onAccent: string };

function card(design: Design): Card {
  const { colors, spec } = design;
  const dark = spec.surface === "dark";
  const background = dark ? mix(INK, colors.block, 0.25) : WHITE;
  const ink = dark ? PAPER : colors.ink;
  const accent = colors.block;
  return { background, ink, muted: alpha(ink, 0.7), accent, onAccent: isDark(accent) ? PAPER : INK };
}

function Backdrop({ design }: { design: Design }) {
  const { spec, colors } = design;
  if (spec.surface === "paper" || spec.surface === "brand") {
    const base = spec.surface === "brand" ? colors.block : colors.paper;
    const dots = alpha(isDark(base) ? PAPER : INK, 0.12);
    return (
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundColor: base,
          backgroundImage: `radial-gradient(${dots} 2px, transparent 2px)`,
          backgroundSize: "36px 36px",
        }}
      />
    );
  }
  return (
    <div style={{ position: "absolute", inset: 0, display: "flex", overflow: "hidden", backgroundColor: colors.ink }}>
      <Photo
        src={spec.image}
        width={WIDTH + 120}
        height={HEIGHT + 150}
        focus={spec.focus}
        style={{ position: "absolute", left: -60, top: -75, filter: "blur(36px) brightness(0.62) saturate(1.1)" }}
      />
    </div>
  );
}

function Header({ design, tone }: { design: Design; tone: Card }) {
  const { spec, type } = design;
  const initial = (spec.brand.name ?? "·").trim().charAt(0).toUpperCase();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 84,
          height: 84,
          borderRadius: 84,
          overflow: "hidden",
          backgroundColor: spec.logo ? PAPER : tone.accent,
          border: `2px solid ${alpha(tone.ink, 0.08)}`,
        }}
      >
        {spec.logo ? (
          <img src={spec.logo.src} alt="" style={{ width: 60, height: 60, objectFit: "contain" }} />
        ) : (
          <div style={{ ...displayStyle(type.display, 44), lineHeight: 1, color: tone.onAccent }}>{initial}</div>
        )}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6, flexGrow: 1 }}>
        <div style={{ ...textStyle(type, 30, type.textBold), lineHeight: 1.1, color: tone.ink }}>{spec.brand.name ?? ""}</div>
        <div style={{ ...textStyle(type, 24), lineHeight: 1.1, color: tone.muted }}>{spec.kicker ?? "Nota"}</div>
      </div>
      <div style={{ ...textStyle(type, 24, 500), lineHeight: 1, color: tone.muted }}>{`${pad(spec.index)}/${pad(spec.count)}`}</div>
    </div>
  );
}

function Frame({ design, children, top }: { design: Design; children: React.ReactNode; top: number }) {
  const tone = card(design);
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT }}>
      <Backdrop design={design} />
      <div
        style={{
          position: "absolute",
          left: CARD_X,
          top,
          width: CARD_WIDTH,
          display: "flex",
          flexDirection: "column",
          padding: PADDING,
          gap: 40,
          borderRadius: 48,
          backgroundColor: tone.background,
          boxShadow: "0 40px 90px rgba(0, 0, 0, 0.28)",
        }}
      >
        <Header design={design} tone={tone} />
        {children}
      </div>
    </div>
  );
}

async function textCard(design: Design) {
  const { spec, type } = design;
  const tone = card(design);
  const cover = spec.role === "cover";
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: INNER,
    maxLines: cover ? 4 : 4,
    sizes: steps(cover ? 120 : 96, 52),
  });
  const body = spec.body
    ? await fit(design, {
        slot: "body",
        text: spec.body,
        style: (size) => textStyle(type, size),
        width: INNER,
        maxLines: 4,
        sizes: steps(38, 32, 2),
      })
    : null;
  const photoHeight = cover ? 360 : 0;
  const cardHeight = PADDING * 2 + 84 + 40 + headline.height + (body ? body.height + 40 : 0) + (cover ? photoHeight + 40 + 66 + 40 : 0);
  const top = Math.max(72, (HEIGHT - cardHeight) / 2);
  return (
    <Frame design={design} top={top}>
      <div style={{ ...displayStyle(type.display, headline.size), color: tone.ink, textWrap: "balance" }}>{spec.headline}</div>
      {body ? <div style={{ ...bodyStyle(type, body), color: tone.muted }}>{spec.body}</div> : null}
      {cover ? (
        <div style={{ display: "flex", width: INNER, height: photoHeight, overflow: "hidden", borderRadius: 28 }}>
          <Photo src={spec.image} width={INNER} height={photoHeight} focus={spec.focus} />
        </div>
      ) : null}
      {cover ? (
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <SwipeCue design={design} color={tone.onAccent} background={tone.accent} />
        </div>
      ) : null}
    </Frame>
  );
}

async function checklist(design: Design) {
  const { spec, type } = design;
  const tone = card(design);
  const entries = spec.items.length ? spec.items : spec.body ? [spec.body] : [];
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: INNER,
    maxLines: 3,
    sizes: steps(88, 52),
  });
  const rows = await Promise.all(
    entries.map((entry, index) =>
      fit(design, {
        slot: `item${index + 1}`,
        text: entry,
        style: (size) => textStyle(type, size, 500),
        width: INNER - 76,
        maxLines: 2,
        sizes: steps(36, 30, 2),
      }),
    ),
  );
  const listHeight = rows.reduce((total, row) => total + Math.max(56, row.height) + 28, 0);
  const cardHeight = PADDING * 2 + 84 + 40 + headline.height + 40 + listHeight;
  const top = Math.max(72, (HEIGHT - cardHeight) / 2);
  return (
    <Frame design={design} top={top}>
      <div style={{ ...displayStyle(type.display, headline.size), color: tone.ink, textWrap: "balance" }}>{spec.headline}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
        {entries.map((entry, index) => (
          <div key={entry} style={{ display: "flex", alignItems: "flex-start", gap: 24 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 52,
                height: 52,
                borderRadius: 52,
                flexShrink: 0,
                backgroundColor: tone.accent,
              }}
            >
              <Icon node={Check} size={30} color={tone.onAccent} strokeWidth={3} />
            </div>
            <div style={{ ...(rows[index] ? bodyStyle(type, rows[index], 500) : textStyle(type, 32, 500)), color: tone.ink, paddingTop: 4 }}>{entry}</div>
          </div>
        ))}
      </div>
    </Frame>
  );
}

async function cta(design: Design) {
  const { spec, type } = design;
  const tone = card(design);
  const headline = await fit(design, {
    slot: "headline",
    text: spec.headline,
    style: (size) => displayStyle(type.display, size),
    width: INNER,
    maxLines: 3,
    sizes: steps(112, 60),
  });
  const body = spec.body
    ? await fit(design, {
        slot: "body",
        text: spec.body,
        style: (size) => textStyle(type, size),
        width: INNER,
        maxLines: 4,
        sizes: steps(36, 30, 2),
      })
    : null;
  const cardHeight = PADDING * 2 + 84 + 40 + headline.height + (body ? body.height + 40 : 0) + 40 + 80;
  const top = Math.max(72, (HEIGHT - cardHeight) / 2);
  return (
    <Frame design={design} top={top}>
      <div style={{ ...displayStyle(type.display, headline.size), color: tone.ink, textWrap: "balance" }}>{spec.headline}</div>
      {body ? <div style={{ ...bodyStyle(type, body), color: tone.muted }}>{spec.body}</div> : null}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <SavePill design={design} color={tone.onAccent} background={tone.accent} />
        <BrandMark design={design} surface={tone.background} height={52} />
      </div>
    </Frame>
  );
}

export function notesLayout(spec: SlideSpec): string {
  if (spec.role === "cta") return "cta";
  if (spec.role === "content" && (spec.layout === "checklist" || (spec.layout === "auto" && spec.items.length > 0))) return "checklist";
  return "card";
}

const LAYOUTS: Record<string, Template> = { card: textCard, checklist, cta };

export async function Notes(design: Design) {
  return (LAYOUTS[design.report.layout] ?? textCard)(design);
}
