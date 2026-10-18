import { BrandMark, Counter, HEIGHT, Kicker, MARGIN, SavePill, SwipeCue, WIDTH, sizeFor } from "../chrome";
import { INK, PAPER, alpha } from "../color";
import { SANS, SERIF } from "../fonts";
import type { SlideSpec } from "../spec";

const LINE_Y = 300;
const DOT = 60;
const COVER_SIZES: [number, number][] = [[16, 136], [30, 116], [48, 96]];
const SLIDE_SIZES: [number, number][] = [[18, 104], [32, 90], [48, 76]];

export function Panorama({ spec }: { spec: SlideSpec }) {
  const cover = spec.role === "cover";
  const dotCenter = MARGIN + DOT / 2;
  const lineLeft = spec.index === 1 ? dotCenter : 0;
  const lineRight = spec.index === spec.count ? WIDTH - dotCenter : 0;
  return (
    <div style={{ position: "relative", display: "flex", width: WIDTH, height: HEIGHT, backgroundColor: INK }}>
      <img src={spec.image} alt="" style={{ position: "absolute", inset: 0, width: WIDTH, height: HEIGHT, objectFit: "cover" }} />
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `linear-gradient(to bottom, ${alpha(INK, 0.62)} 0%, ${alpha(INK, 0.38)} 36%, ${alpha(INK, 0)} 62%, ${alpha(INK, 0)} 80%, ${alpha(INK, 0.55)} 100%)`,
        }}
      />
      {spec.count > 1 ? (
        <div
          style={{
            position: "absolute",
            top: LINE_Y - 1,
            left: lineLeft,
            right: lineRight,
            height: 2,
            backgroundColor: alpha(PAPER, 0.8),
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
          backgroundColor: PAPER,
          fontFamily: SANS,
          fontWeight: 700,
          fontSize: 24,
          color: INK,
        }}
      >
        {spec.index}
      </div>
      <div style={{ position: "absolute", top: LINE_Y - 88, left: MARGIN, display: "flex" }}>
        {spec.kicker ? <Kicker text={spec.kicker} color={PAPER} /> : null}
      </div>
      <div
        style={{
          position: "absolute",
          top: LINE_Y + 64,
          left: MARGIN,
          right: MARGIN,
          display: "flex",
          flexDirection: "column",
          gap: 24,
        }}
      >
        <div
          style={{
            fontFamily: SERIF,
            fontSize: sizeFor(spec.headline, cover ? COVER_SIZES : SLIDE_SIZES, 68),
            lineHeight: 1.03,
            letterSpacing: -0.5,
            color: PAPER,
            textWrap: "balance",
            textShadow: `0 2px 24px ${alpha(INK, 0.35)}`,
          }}
        >
          {spec.headline}
        </div>
        {spec.body ? (
          <div style={{ fontFamily: SANS, fontSize: 32, lineHeight: 1.4, color: alpha(PAPER, 0.92), maxWidth: 800, lineClamp: 3 }}>
            {spec.body}
          </div>
        ) : null}
        {spec.role === "cta" ? (
          <div style={{ display: "flex", marginTop: 8 }}>
            <SavePill color={INK} background={PAPER} />
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
        <BrandMark brand={spec.brand} logo={spec.logo} surface={INK} height={48} />
        {cover ? <SwipeCue color={PAPER} /> : <Counter index={spec.index} count={spec.count} color={alpha(PAPER, 0.8)} />}
      </div>
    </div>
  );
}
