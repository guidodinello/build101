import { timingSafeEqual } from "node:crypto";
import { RENDER_REPORT_HEADER, reportHeader } from "@/lib/post-render/design";
import { renderSlide } from "@/lib/post-render/render";
import { ImageRejectedError, SpecError, parseSlideSpec } from "@/lib/post-render/spec";

// The backend sends a scene and a logo as data URIs, at most about 3.1 MB together; Vercel itself
// rejects bodies over 4.5 MB.
const MAX_BODY_BYTES = 4_000_000;

function authorized(request: Request): boolean {
  const secret = process.env.RENDER_SECRET;
  if (!secret) return false;
  const given = Buffer.from(request.headers.get("authorization") ?? "");
  const expected = Buffer.from(`Bearer ${secret}`);
  return given.length === expected.length && timingSafeEqual(given, expected);
}

// The body as text, or null once it passes the cap. Counts the bytes actually received, since
// Content-Length can be missing (chunked) or wrong.
async function readCapped(request: Request): Promise<string | null> {
  if (!request.body) return "";
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > MAX_BODY_BYTES) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  return Buffer.concat(chunks).toString("utf8");
}

const tooLarge = () => Response.json({ error: "body_too_large" }, { status: 413 });

export async function POST(request: Request) {
  if (!process.env.RENDER_SECRET) return Response.json({ error: "renderer_not_configured" }, { status: 503 });
  if (!authorized(request)) return Response.json({ error: "unauthorized" }, { status: 401 });

  if (Number(request.headers.get("content-length")) > MAX_BODY_BYTES) return tooLarge();
  const text = await readCapped(request);
  if (text === null) return tooLarge();

  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    return Response.json({ error: "invalid_json" }, { status: 400 });
  }

  try {
    const slide = await renderSlide(parseSlideSpec(body));
    return new Response(new Uint8Array(slide.image), {
      headers: {
        "content-type": "image/jpeg",
        "cache-control": "no-store",
        [RENDER_REPORT_HEADER]: reportHeader(slide.report),
      },
    });
  } catch (error) {
    if (error instanceof ImageRejectedError) {
      return Response.json({ error: error.code, detail: error.message }, { status: 422 });
    }
    if (error instanceof SpecError) return Response.json({ error: "invalid_spec", detail: error.message }, { status: 400 });
    throw error;
  }
}
