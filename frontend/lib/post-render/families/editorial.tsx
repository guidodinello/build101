import { BrandMark, Counter, HEIGHT, Kicker, MARGIN, SavePill, SwipeCue, WIDTH, pad, sizeFor } from "../chrome";
import { alpha, palette } from "../color";
import { SANS, SERIF } from "../fonts";
import type { SlideSpec } from "../spec";

const COVER_SIZES: [number, number][] = [[16, 148], [28, 128], [44, 108]];
const CONTENT_SIZES: [number, number][] = [[18, 100], [32, 88], [48, 76]];
const CTA_SIZES: [number, number][] = [[14, 140], [26, 116], [44, 96]];

function Cover({ spec }: { spec: SlideSpec }) {
  const colors = palette(spec.brand.colors);
  const light = colors.paper;
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: colors.ink }}>
      <img src={spec.image} alt="" style={{ position: "absolute", inset: 0, width: WIDTH, height: HEIGHT, objectFit: "cover" }} />
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `linear-gradient(to bottom, ${alpha(colors.ink, 0.5)} 0%, ${alpha(colors.ink, 0)} 24%, ${alpha(colors.ink, 0)} 42%, ${alpha(colors.ink, 0.88)} 100%)`,
        }}
      />
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
        <BrandMark brand={spec.brand} logo={spec.logo} surface={colors.ink} height={56} />
        {spec.kicker ? <Kicker text={spec.kicker} color={light} /> : null}
      </div>
      <div
        style={{
          position: "absolute",
          left: MARGIN,
          right: MARGIN,
          bottom: MARGIN,
          display: "flex",
          flexDirection: "column",
          gap: 28,
        }}
      >
        <div style={{ width: 120, height: 3, backgroundColor: colors.accent }} />
        <div
          style={{
            fontFamily: SERIF,
            fontSize: sizeFor(spec.headline, COVER_SIZES, 92),
            lineHeight: 1.04,
            letterSpacing: -1,
            color: light,
            textWrap: "balance",
          }}
        >
          {spec.headline}
        </div>
        {spec.body ? (
          <div style={{ fontFamily: SANS, fontSize: 34, lineHeight: 1.4, color: alpha(light, 0.88), maxWidth: 820 }}>
            {spec.body}
          </div>
        ) : null}
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
          <SwipeCue color={colors.ink} background={light} />
        </div>
      </div>
    </div>
  );
}

function Content({ spec }: { spec: SlideSpec }) {
  const colors = palette(spec.brand.colors);
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        width: WIDTH,
        height: HEIGHT,
        padding: `80px ${MARGIN}px 72px`,
        backgroundColor: colors.paper,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
        <div style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 52, lineHeight: 1, color: colors.accentOnPaper }}>
          {pad(spec.index - 1)}
        </div>
        <div style={{ flexGrow: 1, height: 2, backgroundColor: alpha(colors.ink, 0.2) }} />
        {spec.kicker ? <Kicker text={spec.kicker} color={alpha(colors.ink, 0.7)} /> : null}
      </div>
      <div style={{ display: "flex", flexGrow: 1, minHeight: 420, marginTop: 40, overflow: "hidden", borderRadius: 6 }}>
        <img src={spec.image} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
      <div
        style={{
          marginTop: 48,
          fontFamily: SERIF,
          fontSize: sizeFor(spec.headline, CONTENT_SIZES, 68),
          lineHeight: 1.04,
          letterSpacing: -0.5,
          color: colors.ink,
          textWrap: "balance",
        }}
      >
        {spec.headline}
      </div>
      {spec.body ? (
        <div
          style={{
            marginTop: 20,
            fontFamily: SANS,
            fontSize: 32,
            lineHeight: 1.4,
            color: alpha(colors.ink, 0.78),
            lineClamp: 3,
          }}
        >
          {spec.body}
        </div>
      ) : null}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 44 }}>
        <BrandMark brand={spec.brand} logo={spec.logo} surface={colors.paper} height={48} />
        <Counter index={spec.index} count={spec.count} color={alpha(colors.ink, 0.6)} />
      </div>
    </div>
  );
}

function Cta({ spec }: { spec: SlideSpec }) {
  const colors = palette(spec.brand.colors);
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        width: WIDTH,
        height: HEIGHT,
        padding: `88px ${MARGIN}px 72px`,
        backgroundColor: colors.block,
      }}
    >
      <BrandMark brand={spec.brand} logo={spec.logo} surface={colors.block} height={72} />
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", flexGrow: 1, gap: 36 }}>
        <div
          style={{
            display: "flex",
            width: 340,
            height: 420,
            overflow: "hidden",
            borderRadius: "170px 170px 12px 12px",
            border: `8px solid ${colors.paper}`,
          }}
        >
          <img src={spec.image} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        </div>
        <div
          style={{
            fontFamily: SERIF,
            fontSize: sizeFor(spec.headline, CTA_SIZES, 84),
            lineHeight: 1.02,
            textAlign: "center",
            color: colors.onBlock,
            textWrap: "balance",
          }}
        >
          {spec.headline}
        </div>
        {spec.body ? (
          <div
            style={{
              fontFamily: SANS,
              fontSize: 34,
              lineHeight: 1.4,
              textAlign: "center",
              color: alpha(colors.onBlock, 0.85),
              maxWidth: 760,
            }}
          >
            {spec.body}
          </div>
        ) : null}
        <SavePill color={colors.block} background={colors.onBlock} />
      </div>
      <Counter index={spec.index} count={spec.count} color={alpha(colors.onBlock, 0.7)} />
    </div>
  );
}

export function Editorial({ spec }: { spec: SlideSpec }) {
  if (spec.role === "cover") return <Cover spec={spec} />;
  if (spec.role === "cta") return <Cta spec={spec} />;
  return <Content spec={spec} />;
}
