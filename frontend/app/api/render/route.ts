import { timingSafeEqual } from "node:crypto";
import { renderSlide } from "@/lib/post-render/render";
import { SpecError, parseSlideSpec } from "@/lib/post-render/spec";

function authorized(request: Request): boolean {
  const secret = process.env.RENDER_SECRET;
  if (!secret) return false;
  const given = Buffer.from(request.headers.get("authorization") ?? "");
  const expected = Buffer.from(`Bearer ${secret}`);
  return given.length === expected.length && timingSafeEqual(given, expected);
}

export async function POST(request: Request) {
  if (!process.env.RENDER_SECRET) return Response.json({ error: "renderer_not_configured" }, { status: 503 });
  if (!authorized(request)) return Response.json({ error: "unauthorized" }, { status: 401 });

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "invalid_json" }, { status: 400 });
  }

  try {
    const image = await renderSlide(parseSlideSpec(body));
    return new Response(new Uint8Array(image), {
      headers: { "content-type": "image/jpeg", "cache-control": "no-store" },
    });
  } catch (error) {
    if (error instanceof SpecError) return Response.json({ error: "invalid_spec", detail: error.message }, { status: 400 });
    throw error;
  }
}
