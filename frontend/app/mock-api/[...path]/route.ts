import * as mock from "@/lib/mock-backend";

// Dev only: it stores uploads in memory and serves them from the app's own origin.
const enabled = () => process.env.ENABLE_MOCK_API === "true" && process.env.VERCEL_ENV !== "production";

type Context = RouteContext<"/mock-api/[...path]">;

async function handle(request: Request, context: Context) {
  if (!enabled()) return new Response(null, { status: 404 });
  const path = (await context.params).path;
  const method = request.method;

  try {
    if (path[0] === "storage") return await storage(request, path[1]);

    const [api, scope, token, ...rest] = path;
    if (api !== "api" || scope !== "o" || !token) return notFound();
    const route = `${method} ${rest.join("/")}`;
    const body = () => request.json();

    if (route === "GET ") return Response.json(mock.getState(token));
    if (route === "PUT business") return Response.json(mock.saveBusiness(token, await body()));
    if (route === "PUT products") return Response.json(mock.saveProducts(token, (await body()).products));
    if (route === "PUT brand") return Response.json(mock.saveBrand(token, await body()));
    if (route === "PUT preferences") return Response.json(mock.savePreferences(token, await body()));
    if (route === "POST uploads") return Response.json(mock.requestUpload(token, await body()));
    if (route === "POST instagram/connect") return Response.json(mock.connectInstagram(token));
    if (route === "POST complete") return Response.json(mock.complete(token), { status: 202 });
    if (rest[0] === "assets" && rest[1]) {
      if (method === "POST" && rest[2] === "complete") {
        return Response.json(mock.completeUpload(token, rest[1]));
      }
      if (method === "DELETE" && rest.length === 2) {
        mock.deleteAsset(token, rest[1]);
        return new Response(null, { status: 204 });
      }
    }
    return notFound();
  } catch (error) {
    if (error instanceof mock.MockError) {
      return Response.json(
        { error: { code: error.code, message: error.message } },
        { status: error.status },
      );
    }
    throw error;
  }
}

async function storage(request: Request, assetId: string | undefined) {
  if (!assetId) return notFound();

  if (request.method === "PUT") {
    const contentType = request.headers.get("content-type") ?? "";
    if (contentType.startsWith("multipart/form-data")) {
      const file = [...(await request.formData()).values()].find((value) => value instanceof File);
      if (!file) return Response.json({ error: { code: "no_file", message: "No file" } }, { status: 400 });
      mock.storeFile(assetId, { bytes: await file.arrayBuffer(), contentType: file.type });
    } else {
      mock.storeFile(assetId, { bytes: await request.arrayBuffer(), contentType });
    }
    return Response.json({ Key: assetId });
  }

  const file = mock.readFile(assetId);
  if (!file) return notFound();
  // The stored type is whatever the client declared: never let the browser render it as a page.
  // `<img>` ignores Content-Disposition, so wizard previews still work.
  return new Response(file.bytes, {
    headers: {
      "Content-Type": file.contentType,
      "X-Content-Type-Options": "nosniff",
      "Content-Disposition": "attachment",
    },
  });
}

function notFound() {
  return Response.json({ error: { code: "not_found", message: "Not found" } }, { status: 404 });
}

export { handle as GET, handle as PUT, handle as POST, handle as DELETE };
