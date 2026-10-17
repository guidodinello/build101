"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { CameraIcon, InfoIcon, RotateCwIcon, XIcon } from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { WizardStep } from "@/components/onboarding/wizard-step";
import { useWizard } from "@/components/onboarding/wizard-context";
import type { PendingPhoto } from "@/components/onboarding/use-photo-uploads";
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
      subtitle="Productos, el taller, el equipo."
      onSubmit={submit}
    >
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold tabular-nums" aria-live="polite">
          {total} de {MAX_PHOTOS}
        </p>
        <p className="text-[13px] text-muted-foreground">Mínimo {MIN_PHOTOS}</p>
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
        {ready.map((asset, index) => (
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

function PhotoTile({
  src,
  label,
  onRemove,
  children,
}: {
  src: string | null;
  label: string;
  onRemove: () => void;
  children?: ReactNode;
}) {
  return (
    <li className="relative aspect-square overflow-hidden rounded-md bg-muted">
      {src && (
        // eslint-disable-next-line @next/next/no-img-element -- signed Storage URLs and object URLs
        <img src={src} alt={label} className="size-full object-cover" />
      )}
      {children}
      <button
        type="button"
        aria-label={`Quitar ${label.toLowerCase()}`}
        className="absolute top-0.5 right-0.5 flex size-8 items-center justify-center rounded-full bg-foreground/60 text-background"
        onClick={onRemove}
      >
        <XIcon className="size-3.5" aria-hidden />
      </button>
    </li>
  );
}

function PendingOverlay({ photo, onRetry }: { photo: PendingPhoto; onRetry: () => void }) {
  if (photo.status === "failed") {
    return (
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 bg-destructive/85 p-2 text-center text-xs font-semibold text-white">
        {photo.retryable ? (
          <button type="button" className="flex flex-col items-center gap-1" onClick={onRetry}>
            <RotateCwIcon className="size-5.5" aria-hidden />
            Reintentar
          </button>
        ) : (
          <span>{photo.error}</span>
        )}
      </div>
    );
  }

  return (
    <div className="absolute inset-0 flex items-center justify-center bg-background/55">
      <ProgressRing value={photo.status === "queued" ? 0 : photo.progress} />
    </div>
  );
}

function ProgressRing({ value }: { value: number }) {
  const radius = 11;
  const circumference = 2 * Math.PI * radius;
  return (
    <svg
      role="progressbar"
      aria-label="Subiendo"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(value * 100)}
      viewBox="0 0 28 28"
      className="size-8 -rotate-90 text-primary"
    >
      <circle cx="14" cy="14" r={radius} fill="none" stroke="currentColor" strokeOpacity={0.2} strokeWidth={3} />
      <circle
        cx="14"
        cy="14"
        r={radius}
        fill="none"
        stroke="currentColor"
        strokeWidth={3}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={circumference * (1 - Math.max(value, 0.04))}
        className="transition-[stroke-dashoffset]"
      />
    </svg>
  );
}
