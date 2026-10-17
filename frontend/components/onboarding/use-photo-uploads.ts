"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, type Asset } from "@/lib/api";
import { uploadAsset, validatePhoto, type UploadHandle } from "@/lib/upload";

const MAX_PARALLEL = 3;

export type PendingPhoto = {
  id: string;
  file: File;
  previewUrl: string;
  status: "queued" | "uploading" | "failed";
  progress: number;
  error: string | null;
  retryable: boolean;
};

export type PhotoUploads = ReturnType<typeof usePhotoUploads>;

let nextId = 0;

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

export function usePhotoUploads(token: string, onUploaded: (asset: Asset) => void) {
  const [pending, setPending] = useState<PendingPhoto[]>([]);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const queue = useRef<PendingPhoto[]>([]);
  const handles = useRef(new Map<string, UploadHandle>());
  const onUploadedRef = useRef(onUploaded);

  useEffect(() => {
    onUploadedRef.current = onUploaded;
  }, [onUploaded]);

  const inFlight = pending.filter((photo) => photo.status !== "failed").length;

  useEffect(() => {
    if (inFlight === 0) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [inFlight]);

  function patch(id: string, changes: Partial<PendingPhoto>) {
    setPending((list) => list.map((photo) => (photo.id === id ? { ...photo, ...changes } : photo)));
  }

  function pump() {
    while (handles.current.size < MAX_PARALLEL && queue.current.length > 0) {
      const photo = queue.current.shift()!;
      patch(photo.id, { status: "uploading", progress: 0, error: null });

      const handle = uploadAsset(token, "photo", photo.file, (progress) =>
        patch(photo.id, { progress }),
      );
      handles.current.set(photo.id, handle);

      handle.promise
        .then(
          (asset) => {
            setPreviews((current) => ({ ...current, [asset.id]: photo.previewUrl }));
            setPending((list) => list.filter((item) => item.id !== photo.id));
            onUploadedRef.current(asset);
          },
          (error: unknown) => {
            if (isAbort(error)) return;
            const rejected = error instanceof ApiError && error.status === 422;
            patch(photo.id, {
              status: "failed",
              error: rejected ? error.message : null,
              retryable: !rejected,
            });
          },
        )
        .finally(() => {
          handles.current.delete(photo.id);
          pump();
        });
    }
  }

  function add(files: File[]) {
    const photos = files.map<PendingPhoto>((file) => {
      const error = validatePhoto(file);
      return {
        id: `photo-${nextId++}`,
        file,
        previewUrl: URL.createObjectURL(file),
        status: error ? "failed" : "queued",
        progress: 0,
        error,
        retryable: false,
      };
    });
    setPending((list) => [...list, ...photos]);
    queue.current.push(...photos.filter((photo) => photo.status === "queued"));
    pump();
  }

  function retry(id: string) {
    const photo = pending.find((item) => item.id === id);
    if (!photo?.retryable) return;
    patch(id, { status: "queued", error: null });
    queue.current.push(photo);
    pump();
  }

  function remove(id: string) {
    handles.current.get(id)?.abort();
    queue.current = queue.current.filter((photo) => photo.id !== id);
    const photo = pending.find((item) => item.id === id);
    if (photo) URL.revokeObjectURL(photo.previewUrl);
    setPending((list) => list.filter((item) => item.id !== id));
  }

  return { pending, previews, inFlight, add, retry, remove };
}
