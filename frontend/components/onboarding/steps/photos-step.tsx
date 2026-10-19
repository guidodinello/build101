"use client";

import { useEffect, useRef, useState } from "react";
import { CameraIcon } from "lucide-react";
import { toast } from "sonner";
import { Spinner } from "@/components/ui/spinner";
import { WizardStep } from "@/components/onboarding/wizard-step";
import { useWizard } from "@/components/onboarding/wizard-context";
import { PendingOverlay, PhotoTile } from "@/components/onboarding/photo-tile";
import { messageOf, onboardingApi, type Asset, type OnboardingState } from "@/lib/api";
import {
  atHandle,
  instagramPhotos,
  isInstagramConnected,
  MAX_PHOTOS,
  MIN_PHOTOS,
  ownPhotos,
  readyPhotos,
} from "@/lib/onboarding";

const POLL_MS = 3000;
const IMPORT_WAIT_MS = 90_000;

export function PhotosStep() {
  const { token, state, setState, goTo, photoUploads } = useWizard();
  const { pending, previews, inFlight, add, retry, remove } = photoUploads;
  const [error, setError] = useState<string | null>(null);
  const [importTimedOut, setImportTimedOut] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const deletedIds = useRef(new Set<string>());

  const own = ownPhotos(state);
  const general = own.filter((asset) => asset.product_ids.length === 0);
  const ofProducts = own.length - general.length;
  const imported = instagramPhotos(state);
  const ready = readyPhotos(state).length;
  const total = ready + inFlight;
  const ownTotal = own.length + inFlight;
  const analyzing = readyPhotos(state).some((asset) => !asset.analyzed);
  const importing = isInstagramConnected(state) && imported.length === 0 && !importTimedOut;

  useEffect(() => {
    if (!importing) return;
    const timer = window.setTimeout(() => setImportTimedOut(true), IMPORT_WAIT_MS);
    return () => window.clearTimeout(timer);
  }, [importing]);

  useEffect(() => {
    if (!analyzing && !importing) return;
    const timer = window.setInterval(async () => {
      const fresh = await onboardingApi.getState(token).catch(() => null);
      if (fresh) setState((current) => mergeAssets(current, fresh, deletedIds.current));
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [analyzing, importing, token, setState]);

  function addFiles(files: File[]) {
    const room = MAX_PHOTOS - ownTotal;
    if (files.length > room) toast(`Podés subir hasta ${MAX_PHOTOS} fotos. Sumé las primeras ${room}.`);
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
    if (ready >= MIN_PHOTOS) {
      goTo("brand");
      return;
    }
    setError(
      total >= MIN_PHOTOS
        ? "Esperá un toque que terminen de subir."
        : `Sumá ${MIN_PHOTOS - total === 1 ? "1 foto más" : `${MIN_PHOTOS - total} fotos más`}, así tengo con qué trabajar.`,
    );
  }

  const handle = state.instagram.handle ? atHandle(state.instagram.handle) : "tu Instagram";

  return (
    <WizardStep
      step="photos"
      title="Mandame tus fotos"
      subtitle={
        ofProducts > 0
          ? "El taller, el equipo, tus trabajos. Uso tus fotos reales, sin cambiar tu producto."
          : "Productos, el lugar, el equipo. Uso tus fotos reales, sin cambiar tu producto."
      }
      onSubmit={submit}
    >
      <p className="-mb-3 flex items-baseline justify-between text-[15px]" aria-live="polite">
        <span className="font-bold tabular-nums">
          {total} {total === 1 ? "foto" : "fotos"}
        </span>
        <span className="text-muted-foreground">
          {ofProducts > 0 && `${ofProducts} de tus productos · `}Mínimo {MIN_PHOTOS}
        </span>
      </p>

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
        {ownTotal < MAX_PHOTOS && (
          <li>
            <button
              type="button"
              className="flex aspect-square w-full flex-col items-center justify-center gap-1.5 rounded-md border-[1.5px] border-dashed border-input bg-card text-sm font-bold text-primary outline-none focus-visible:ring-3 focus-visible:ring-primary/40"
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
            {!asset.analyzed && <LookingChip />}
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
        <p role="alert" className="text-[15px] font-medium text-destructive">
          {error}
        </p>
      )}

      {(imported.length > 0 || importing) && (
        <section aria-labelledby="instagram-photos" className="flex flex-col gap-3">
          <div className="flex flex-col gap-0.5">
            <h2 id="instagram-photos" className="font-heading text-lg font-extrabold tracking-tight">
              De {handle}
            </h2>
            <p className="text-[15px] leading-snug text-muted-foreground">
              {importing
                ? "Las estoy trayendo, tarda un minuto. Podés seguir y las sumo igual."
                : "También cuentan. Sacá las que no quieras que use."}
            </p>
          </div>
          {importing ? (
            <ul className="grid grid-cols-3 gap-2" aria-busy>
              {[0, 1, 2].map((slot) => (
                <li
                  key={slot}
                  className="flex aspect-square items-center justify-center rounded-md bg-card/70 shadow-[inset_0_0_0_1px_var(--border)]"
                >
                  {slot === 1 && <Spinner className="size-5 text-muted-foreground" aria-label="Trayendo fotos" />}
                </li>
              ))}
            </ul>
          ) : (
            <ul className="grid grid-cols-3 gap-2">
              {imported.map((asset, index) => (
                <PhotoTile
                  key={asset.id}
                  src={asset.thumbnail_url ?? asset.url}
                  label={`Foto ${index + 1} de Instagram`}
                  onRemove={() => removeAsset(asset)}
                >
                  {!asset.analyzed && <LookingChip />}
                </PhotoTile>
              ))}
            </ul>
          )}
        </section>
      )}
    </WizardStep>
  );
}

function LookingChip() {
  return (
    <span className="absolute bottom-1.5 left-1.5 rounded-full bg-primary/80 px-2 py-0.5 text-[11px] font-semibold text-primary-foreground">
      Mirando…
    </span>
  );
}

function mergeAssets(current: OnboardingState, fresh: OnboardingState, deleted: Set<string>) {
  const freshIds = new Set(fresh.assets.map((asset) => asset.id));
  const localOnly = current.assets.filter((asset) => !freshIds.has(asset.id));
  const assets = [...fresh.assets, ...localOnly].filter((asset) => !deleted.has(asset.id));
  return { ...current, assets };
}
