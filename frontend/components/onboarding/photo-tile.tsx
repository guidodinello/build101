import type { ReactNode } from "react";
import { RotateCwIcon, XIcon } from "lucide-react";
import type { PendingPhoto } from "@/components/onboarding/use-photo-uploads";

export function PhotoTile({
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
        className="absolute top-1 right-1 flex size-8 items-center justify-center rounded-full bg-primary/70 text-primary-foreground backdrop-blur-sm"
        onClick={onRemove}
      >
        <XIcon className="size-3.5" aria-hidden />
      </button>
    </li>
  );
}

export function PendingOverlay({ photo, onRetry }: { photo: PendingPhoto; onRetry: () => void }) {
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
