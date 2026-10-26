import { RENDER_REPORT_HEADER, reportHeader } from "@/lib/post-render/design";
import { previewEnabled } from "@/lib/post-render/preview";
import { renderSlide } from "@/lib/post-render/render";
import { SAMPLE_SLIDES, sampleOptions, sampleSpec } from "@/lib/post-render/samples";
import { FAMILIES } from "@/lib/post-render/spec";

export async function GET(request: Request) {
  if (!previewEnabled()) return new Response(null, { status: 404 });
  const params = new URL(request.url).searchParams;
  const family = FAMILIES.find((name) => name === params.get("family"));
  const index = Number(params.get("index") ?? "1");
  if (!family || !Number.isInteger(index) || index < 1 || index > SAMPLE_SLIDES.length) {
    return Response.json({ error: "unknown_sample" }, { status: 400 });
  }
  const slide = await renderSlide(await sampleSpec(sampleOptions(params, family, index)));
  return new Response(new Uint8Array(slide.image), {
    headers: { "content-type": "image/jpeg", "cache-control": "no-store", [RENDER_REPORT_HEADER]: reportHeader(slide.report) },
  });
}
