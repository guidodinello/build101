import { ArrowRight } from "lucide";
import { BrandMark, Counter, HEIGHT, Kicker, MARGIN, SavePill, WIDTH, pad, sizeFor } from "../chrome";
import { alpha, palette, type Palette } from "../color";
import { GROTESK, SANS } from "../fonts";
import { Icon } from "../icon";
import type { SlideSpec } from "../spec";

const LINE_Y = 680;
const NODE = 180;
const COVER_SIZES: [number, number][] = [[16, 140], [30, 120], [48, 100]];
const CONTENT_SIZES: [number, number][] = [[20, 80], [36, 70], [56, 60]];
const CTA_SIZES: [number, number][] = [[14, 124], [28, 104], [48, 84]];

function SeamNodes({ spec, color }: { spec: SlideSpec; color: string }) {
  const top = LINE_Y - NODE / 2;
  const node = { position: "absolute", top, width: NODE, height: NODE, borderRadius: NODE, backgroundColor: color } as const;
  return (
    <>
      {spec.index > 1 ? <div style={{ ...node, left: -NODE / 2 }} /> : null}
      {spec.index < spec.count ? <div style={{ ...node, right: -NODE / 2 }} /> : null}
    </>
  );
}

function Timeline({ colors }: { colors: Palette }) {
  return <div style={{ position: "absolute", top: LINE_Y - 2, left: 0, width: WIDTH, height: 4, backgroundColor: colors.accentOnPaper }} />;
}

function Cover({ spec }: { spec: SlideSpec }) {
  const colors = palette(spec.brand.colors);
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: colors.block }}>
      <div
        style={{
          position: "absolute",
          right: MARGIN,
          bottom: 0,
          display: "flex",
          width: 520,
          height: 640,
          overflow: "hidden",
          borderRadius: "260px 260px 0 0",
        }}
      >
        <img src={spec.image} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
      <SeamNodes spec={spec} color={colors.accent} />
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
          <div style={{ display: "flex", padding: "12px 24px", borderRadius: 999, border: `2px solid ${colors.onBlock}` }}>
            <Kicker text={spec.kicker} color={colors.onBlock} />
          </div>
        ) : (
          <div />
        )}
        <BrandMark brand={spec.brand} logo={spec.logo} surface={colors.block} height={56} />
      </div>
      <div
        style={{
          position: "absolute",
          top: 210,
          left: MARGIN,
          width: 860,
          fontFamily: GROTESK,
          fontWeight: 800,
          fontSize: sizeFor(spec.headline, COVER_SIZES, 88),
          lineHeight: 0.98,
          letterSpacing: -3,
          color: colors.onBlock,
          textWrap: "balance",
        }}
      >
        {spec.headline}
      </div>
      {spec.body ? (
        <div
          style={{
            position: "absolute",
            left: MARGIN,
            bottom: 280,
            width: 320,
            fontFamily: SANS,
            fontSize: 30,
            lineHeight: 1.35,
            color: alpha(colors.onBlock, 0.88),
            lineClamp: 5,
          }}
        >
          {spec.body}
        </div>
      ) : null}
      <div
        style={{
          position: "absolute",
          left: MARGIN,
          bottom: MARGIN,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 132,
          height: 132,
          borderRadius: 132,
          backgroundColor: colors.onBlock,
        }}
      >
        <Icon node={ArrowRight} size={56} color={colors.block} strokeWidth={2.25} />
      </div>
    </div>
  );
}

function Content({ spec }: { spec: SlideSpec }) {
  const colors = palette(spec.brand.colors);
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: colors.paper }}>
      <div style={{ position: "absolute", top: 0, left: 0, display: "flex", width: WIDTH, height: LINE_Y, overflow: "hidden" }}>
        <img src={spec.image} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
      <Timeline colors={colors} />
      <SeamNodes spec={spec} color={colors.accent} />
      <div
        style={{
          position: "absolute",
          top: LINE_Y + 36,
          left: MARGIN,
          right: MARGIN,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
        }}
      >
        <div
          style={{
            fontFamily: GROTESK,
            fontWeight: 800,
            fontSize: 210,
            lineHeight: 0.86,
            letterSpacing: -10,
            color: colors.accentOnPaper,
          }}
        >
          {pad(spec.index - 1)}
        </div>
        {spec.kicker ? <Kicker text={spec.kicker} color={alpha(colors.ink, 0.6)} /> : null}
      </div>
      <div
        style={{
          position: "absolute",
          top: LINE_Y + 268,
          left: MARGIN,
          right: MARGIN,
          display: "flex",
          flexDirection: "column",
          gap: 18,
        }}
      >
        <div
          style={{
            fontFamily: GROTESK,
            fontWeight: 800,
            fontSize: sizeFor(spec.headline, CONTENT_SIZES, 52),
            lineHeight: 1,
            letterSpacing: -1.5,
            color: colors.ink,
            textWrap: "balance",
          }}
        >
          {spec.headline}
        </div>
        {spec.body ? (
          <div style={{ fontFamily: SANS, fontSize: 30, lineHeight: 1.4, color: alpha(colors.ink, 0.75), lineClamp: 2 }}>
            {spec.body}
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
        <BrandMark brand={spec.brand} logo={spec.logo} surface={colors.paper} height={44} />
        <Counter index={spec.index} count={spec.count} color={alpha(colors.ink, 0.55)} />
      </div>
    </div>
  );
}

function Cta({ spec }: { spec: SlideSpec }) {
  const colors = palette(spec.brand.colors);
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: colors.block }}>
      <SeamNodes spec={spec} color={colors.accent} />
      <div
        style={{
          position: "absolute",
          top: 160,
          left: MARGIN,
          right: MARGIN,
          display: "flex",
          flexDirection: "column",
          gap: 32,
        }}
      >
        <div
          style={{
            fontFamily: GROTESK,
            fontWeight: 800,
            fontSize: sizeFor(spec.headline, CTA_SIZES, 72),
            lineHeight: 0.98,
            letterSpacing: -3,
            color: colors.onBlock,
            textWrap: "balance",
          }}
        >
          {spec.headline}
        </div>
        {spec.body ? (
          <div style={{ fontFamily: SANS, fontSize: 34, lineHeight: 1.4, color: alpha(colors.onBlock, 0.88), maxWidth: 780 }}>
            {spec.body}
          </div>
        ) : null}
        <div style={{ display: "flex" }}>
          <SavePill color={colors.block} background={colors.onBlock} />
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          right: MARGIN,
          bottom: 180,
          display: "flex",
          width: 380,
          height: 380,
          overflow: "hidden",
          borderRadius: 380,
          border: `8px solid ${colors.onBlock}`,
        }}
      >
        <img src={spec.image} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
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
        <BrandMark brand={spec.brand} logo={spec.logo} surface={colors.block} height={56} />
        <Counter index={spec.index} count={spec.count} color={alpha(colors.onBlock, 0.7)} />
      </div>
    </div>
  );
}

export function Numbers({ spec }: { spec: SlideSpec }) {
  if (spec.role === "cover") return <Cover spec={spec} />;
  if (spec.role === "cta") return <Cta spec={spec} />;
  return <Content spec={spec} />;
}
