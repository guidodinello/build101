import { onboardingApi, type Asset, type AssetKind } from "@/lib/api";

export const MAX_PHOTO_BYTES = 10 * 1024 * 1024;

const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp", "image/heic"];
const HEIC_EXTENSIONS = /\.(heic|heif)$/i;

export const UNSUPPORTED_FILE = "Este archivo no lo podemos usar. Subí fotos.";
export const FILE_TOO_BIG = "Esta foto pesa más de 10 MB. Probá con otra.";

// iOS Safari often reports HEIC files with an empty type, so fall back to the extension.
export function contentTypeOf(file: File) {
  if (file.type) return file.type === "image/heif" ? "image/heic" : file.type;
  return HEIC_EXTENSIONS.test(file.name) ? "image/heic" : "";
}

export function validatePhoto(file: File): string | null {
  if (!PHOTO_TYPES.includes(contentTypeOf(file))) return UNSUPPORTED_FILE;
  if (file.size > MAX_PHOTO_BYTES) return FILE_TOO_BIG;
  return null;
}

export type UploadHandle = {
  promise: Promise<Asset>;
  abort: () => void;
};

export function uploadAsset(
  token: string,
  kind: AssetKind,
  file: File,
  onProgress: (fraction: number) => void,
): UploadHandle {
  const xhr = new XMLHttpRequest();
  let aborted = false;

  const promise = (async () => {
    const ticket = await onboardingApi.requestUpload(token, {
      kind,
      filename: file.name,
      content_type: contentTypeOf(file),
      size_bytes: file.size,
    });
    if (aborted) throw new DOMException("Upload aborted", "AbortError");

    await putToSignedUrl(xhr, ticket.upload_url, file, onProgress);
    if (aborted) throw new DOMException("Upload aborted", "AbortError");
    return onboardingApi.completeUpload(token, ticket.asset_id);
  })();

  return {
    promise,
    abort: () => {
      aborted = true;
      xhr.abort();
    },
  };
}

// Same body shape as supabase-js `uploadToSignedUrl`, so the signed Supabase URL accepts it as is.
function putToSignedUrl(
  xhr: XMLHttpRequest,
  url: string,
  file: File,
  onProgress: (fraction: number) => void,
) {
  return new Promise<void>((resolve, reject) => {
    const body = new FormData();
    body.append("cacheControl", "3600");
    body.append("", file);

    xhr.open("PUT", url);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new Error(`Upload failed with status ${xhr.status}`));
    xhr.onerror = () => reject(new Error("Upload failed"));
    xhr.onabort = () => reject(new DOMException("Upload aborted", "AbortError"));
    xhr.send(body);
  });
}
