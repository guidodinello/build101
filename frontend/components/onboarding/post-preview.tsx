import { ImageIcon } from "lucide-react";
import { Label } from "@/components/landing/chat";
import { readableOn } from "@/lib/post-render/color";

const NEUTRAL_FRAME = "#e9e4da";
const NEUTRAL_MARK = "#2f3a34";

type PostPreviewProps = {
  name: string;
  location: string | null;
  caption: string | null;
  photoUrl: string | null;
  logoUrl: string | null;
  colors: string[];
};

export function PostPreview({ name, location, caption, photoUrl, logoUrl, colors }: PostPreviewProps) {
  const mark = colors[0] ?? NEUTRAL_MARK;
  const frame = colors[1] ?? colors[0] ?? NEUTRAL_FRAME;

  return (
    <figure
      aria-label="Ejemplo de cómo se vería un post tuyo"
      className="overflow-hidden rounded-[22px] bg-card shadow-bubble motion-safe:animate-rise motion-safe:[animation-delay:.15s]"
    >
      <div className="flex items-center gap-2.5 px-3.5 py-3">
        <span
          aria-hidden
          className="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-full font-heading text-sm font-extrabold ring-[1.5px] ring-accent ring-offset-2 transition-colors duration-500"
          style={{ background: logoUrl ? "#ffffff" : mark, color: readableOn(mark, ["#ffffff", "#0b1f17"]) }}
        >
          {logoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element -- signed Storage URL
            <img src={logoUrl} alt="" className="size-full object-contain p-0.5" />
          ) : (
            name.trim().charAt(0).toUpperCase() || "N"
          )}
        </span>
        <span className="flex min-w-0 flex-col">
          <span className="truncate text-sm font-bold">{name}</span>
          {location && <span className="truncate text-xs font-medium text-ld-subtle">{location}</span>}
        </span>
        <Label className="ml-auto">Ejemplo</Label>
      </div>
      <div className="px-5 pt-5 pb-6 transition-colors duration-500" style={{ background: frame }}>
        {photoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element -- signed Storage URLs and object URLs
          <img
            src={photoUrl}
            alt=""
            className="h-52 w-full rounded-md object-cover shadow-[0_22px_34px_-20px_rgb(20_20_20/0.6)]"
          />
        ) : (
          <div className="flex h-52 w-full items-center justify-center rounded-md bg-white/40 text-foreground/50">
            <ImageIcon className="size-8" aria-hidden />
          </div>
        )}
      </div>
      {caption && (
        <figcaption className="px-3.5 pt-3 pb-3.5 text-[15px] leading-snug">
          <strong>{name}</strong> {caption}
        </figcaption>
      )}
    </figure>
  );
}
