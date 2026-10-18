"use client";

import { useEffect, useRef, useState } from "react";
import { CameraIcon, InfoIcon } from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { WizardStep } from "@/components/onboarding/wizard-step";
import { useWizard } from "@/components/onboarding/wizard-context";
import { PendingOverlay, PhotoTile } from "@/components/onboarding/photo-tile";
import { messageOf, onboardingApi, type Asset } from "@/lib/api";
import { MAX_PHOTOS, MIN_PHOTOS, readyPhotos } from "@/lib/onboarding";

const ANALYSIS_POLL_MS = 3000;

export function PhotosStep() {
  const { token, state, setState, goTo, photoUploads } = useWizard();
  const { pending, previews, inFlight, add, retry, remove } = photoUploads;
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const deletedIds = useRef(new Set<string>());

  const ready = readyPhotos(state);
  const general = ready.filter((asset) => asset.product_ids.length === 0);
  const ofProducts = ready.length - general.length;
  const total = ready.length + inFlight;
  const analyzing = ready.some((asset) => !asset.analyzed);

  useEffect(() => {
    if (!analyzing) return;
    const timer = window.setInterval(async () => {
      const fresh = await onboardingApi.getState(token).catch(() => null);
      if (!fresh) return;
      setState((current) => {
        const freshIds = new Set(fresh.assets.map((asset) => asset.id));
        const localOnly = current.assets.filter((asset) => !freshIds.has(asset.id));
        const assets = [...fresh.assets, ...localOnly].filter(
          (asset) => !deletedIds.current.has(asset.id),
        );
        return { ...current, assets };
      });
    }, ANALYSIS_POLL_MS);
    return () => window.clearInterval(timer);
  }, [analyzing, token, setState]);

  function addFiles(files: File[]) {
    const room = MAX_PHOTOS - total;
    if (files.length > room) toast(`Podés subir hasta ${MAX_PHOTOS} fotos. Sumamos las primeras ${room}.`);
    add(files.slice(0, room));
    setError(null);
  }

  async function removeAsset(asset: Asset) {
    deletedIds.current.add(asset.id);
    setState((current) => ({
      ...current,
      assets: current.assets.filter((item) => item.id !== asset.id),
    }));
    try {
      await onboardingApi.deleteAsset(token, asset.id);
    } catch (removeError) {
      deletedIds.current.delete(asset.id);
      setState((current) => ({ ...current, assets: [...current.assets, asset] }));
      toast.error(messageOf(removeError));
    }
  }

  function submit() {
    if (ready.length >= MIN_PHOTOS) {
      goTo("preferences");
      return;
    }
    setError(
      total >= MIN_PHOTOS
        ? "Esperá un toque que terminen de subir."
        : `Subí al menos ${MIN_PHOTOS} fotos.`,
    );
  }

  return (
    <WizardStep
      step="photos"
      title="Tus fotos"
      subtitle={
        ofProducts > 0
          ? "El taller, el equipo, tus trabajos."
          : "Productos, el taller, el equipo."
      }
      onSubmit={submit}
    >
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold tabular-nums" aria-live="polite">
          {total} de {MAX_PHOTOS}
        </p>
        <p className="text-[13px] text-muted-foreground">
          {ofProducts > 0 && `${ofProducts} de tus productos · `}Mínimo {MIN_PHOTOS}
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

      <ul className="grid grid-cols-3 gap-2">
        {total < MAX_PHOTOS && (
          <li>
            <button
              type="button"
              className="flex aspect-square w-full flex-col items-center justify-center gap-1.5 rounded-md border-[1.5px] border-dashed border-input bg-card text-[13px] font-semibold text-primary outline-none focus-visible:ring-3 focus-visible:ring-ring/40"
              onClick={() => fileInput.current?.click()}
            >
              <CameraIcon className="size-6.5" aria-hidden />
              Agregar
            </button>
          </li>
        )}
        {general.map((asset, index) => (
          <PhotoTile
            key={asset.id}
            src={previews[asset.id] ?? asset.thumbnail_url ?? asset.url}
            label={`Foto ${index + 1}`}
            onRemove={() => removeAsset(asset)}
          >
            {!asset.analyzed && (
              <span className="absolute bottom-1.5 left-1.5 rounded-full bg-foreground/70 px-2 py-0.5 text-[11px] font-semibold text-background">
                Mirando…
              </span>
            )}
          </PhotoTile>
        ))}
        {pending.map((photo, index) => (
          <PhotoTile
            key={photo.id}
            src={photo.file.type.startsWith("image/") ? photo.previewUrl : null}
            label={`Foto nueva ${index + 1}`}
            onRemove={() => remove(photo.id)}
          >
            <PendingOverlay photo={photo} onRetry={() => retry(photo.id)} />
          </PhotoTile>
        ))}
      </ul>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      <Alert role="note" className="border-0 bg-callout px-3.5 py-3 text-callout-foreground">
        <InfoIcon aria-hidden />
        <AlertDescription className="text-[13.5px] leading-snug text-callout-foreground">
          Usamos tus fotos reales en los posts. Nada se publica sin que lo apruebes.
        </AlertDescription>
      </Alert>
    </WizardStep>
  );
}
