"use client";

import { useEffect, useRef } from "react";
import { CameraIcon } from "lucide-react";
import { toast } from "sonner";
import { PendingOverlay, PhotoTile } from "@/components/onboarding/photo-tile";
import { usePhotoUploads } from "@/components/onboarding/use-photo-uploads";
import { useWizard } from "@/components/onboarding/wizard-context";
import { messageOf, onboardingApi, type Asset } from "@/lib/api";
import { MAX_PRODUCT_PHOTOS } from "@/lib/onboarding";

type ProductPhotosProps = {
  productLabel: string;
  assetIds: string[];
  room: number;
  onChange: (assetIds: (current: string[]) => string[]) => void;
  onUploadingChange: (count: number) => void;
};

export function ProductPhotos({
  productLabel,
  assetIds,
  room,
  onChange,
  onUploadingChange,
}: ProductPhotosProps) {
  const { token, state, setState, upsertAsset } = useWizard();
  const fileInput = useRef<HTMLInputElement>(null);
  const { pending, previews, inFlight, add, retry, remove } = usePhotoUploads(
    token,
    (asset: Asset) => {
      upsertAsset(asset);
      onChange((current) => [...current, asset.id]);
    },
  );

  useEffect(() => {
    onUploadingChange(inFlight);
  }, [inFlight, onUploadingChange]);

  const photos = assetIds
    .map((id) => state.assets.find((asset) => asset.id === id))
    .filter((asset): asset is Asset => asset !== undefined);
  const count = photos.length + inFlight;
  const canAdd = count < MAX_PRODUCT_PHOTOS && room > 0;

  function addFiles(files: File[]) {
    const fits = Math.min(MAX_PRODUCT_PHOTOS - count, room);
    if (files.length > fits) {
      toast(`Podés sumar ${fits === 1 ? "1 foto más" : `${fits} fotos más`} a este producto.`);
    }
    add(files.slice(0, fits));
  }

  async function removeAsset(asset: Asset) {
    onChange((current) => current.filter((id) => id !== asset.id));
    setState((current) => ({
      ...current,
      assets: current.assets.filter((item) => item.id !== asset.id),
    }));
    try {
      await onboardingApi.deleteAsset(token, asset.id);
    } catch (error) {
      onChange((current) => [...current, asset.id]);
      setState((current) => ({ ...current, assets: [...current.assets, asset] }));
      toast.error(messageOf(error));
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <p className="text-sm font-medium">
          Fotos <span className="font-normal text-muted-foreground">(opcional)</span>
        </p>
        <p className="text-[13px] text-muted-foreground tabular-nums" aria-live="polite">
          {count} de {MAX_PRODUCT_PHOTOS}
        </p>
      </div>

      <input
        ref={fileInput}
        type="file"
        multiple
        accept="image/jpeg,image/png,image/webp,image/heic,.heic"
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          event.target.value = "";
          if (files.length) addFiles(files);
        }}
      />

      <ul className="grid grid-cols-4 gap-2">
        {photos.map((asset, index) => (
          <PhotoTile
            key={asset.id}
            src={previews[asset.id] ?? asset.thumbnail_url ?? asset.url}
            label={`Foto ${index + 1} de ${productLabel}`}
            onRemove={() => removeAsset(asset)}
          />
        ))}
        {pending.map((photo, index) => (
          <PhotoTile
            key={photo.id}
            src={photo.file.type.startsWith("image/") ? photo.previewUrl : null}
            label={`Foto nueva ${index + 1} de ${productLabel}`}
            onRemove={() => remove(photo.id)}
          >
            <PendingOverlay photo={photo} onRetry={() => retry(photo.id)} />
          </PhotoTile>
        ))}
        {canAdd && (
          <li>
            <button
              type="button"
              aria-label={`Sumar fotos de ${productLabel}`}
              className="flex aspect-square w-full flex-col items-center justify-center gap-1 rounded-md border-[1.5px] border-dashed border-input bg-background text-xs font-semibold text-primary outline-none focus-visible:ring-3 focus-visible:ring-ring/40"
              onClick={() => fileInput.current?.click()}
            >
              <CameraIcon className="size-5.5" aria-hidden />
              Sumar
            </button>
          </li>
        )}
      </ul>
    </div>
  );
}
