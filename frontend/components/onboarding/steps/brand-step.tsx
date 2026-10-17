"use client";

import { useRef, useState } from "react";
import { CheckIcon, ImageUpIcon, PlusIcon, XIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
  FieldLabel,
  FieldLegend,
  FieldSet,
  FieldTitle,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { WizardStep } from "@/components/onboarding/wizard-step";
import { useWizard } from "@/components/onboarding/wizard-context";
import { messageOf, onboardingApi } from "@/lib/api";
import { currentLogo } from "@/lib/onboarding";
import { uploadAsset, validatePhoto } from "@/lib/upload";

const MAX_COLORS = 5;
const NEW_COLOR = "#c89b6d";
const WORD_PLACEHOLDERS = ["Ej: cálidos", "Ej: artesanales", "Ej: confiables"];

type LogoUpload = {
  fileName: string;
  previewUrl: string;
  progress: number;
  failed: boolean;
};

export function BrandStep() {
  const { token, state, setState, upsertAsset, goTo } = useWizard();
  const logo = currentLogo(state);
  const [noBrandYet, setNoBrandYet] = useState(
    !logo && state.brand.colors.length === 0 && state.brand.three_words.length === 3,
  );
  const [colors, setColors] = useState(() =>
    state.brand.colors.length > 0 ? state.brand.colors : (logo?.palette ?? []),
  );
  const [words, setWords] = useState(() =>
    [0, 1, 2].map((index) => state.brand.three_words[index] ?? ""),
  );
  const [upload, setUpload] = useState<LogoUpload | null>(null);
  const [uploadedName, setUploadedName] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [pending, setPending] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const uploading = !!upload && !upload.failed;
  const errors = {
    colors: !noBrandYet && colors.length === 0 && "Sumá al menos un color, o subí tu logo.",
    words: words.some((word) => !word.trim()) && "Completá las 3 palabras.",
  };
  const show = (error: string | false) => (submitted ? error : false);

  async function uploadLogo(file: File) {
    const invalid = validatePhoto(file);
    if (invalid) {
      toast.error(invalid);
      return;
    }

    const previewUrl = URL.createObjectURL(file);
    setUpload({ fileName: file.name, previewUrl, progress: 0, failed: false });
    try {
      const asset = await uploadAsset(token, "logo", file, (progress) =>
        setUpload((current) => current && { ...current, progress }),
      ).promise;
      if (logo) {
        onboardingApi.deleteAsset(token, logo.id).catch(() => undefined);
        setState((current) => ({
          ...current,
          assets: current.assets.filter((item) => item.id !== logo.id),
        }));
      }
      upsertAsset(asset);
      if (asset.palette?.length) setColors(asset.palette.slice(0, MAX_COLORS));
      setUploadedName(file.name);
      setUpload(null);
    } catch (error) {
      setUpload((current) => current && { ...current, failed: true });
      toast.error(messageOf(error));
    }
  }

  async function submit() {
    setSubmitted(true);
    if (errors.colors || errors.words || uploading) return;

    setPending(true);
    try {
      const next = await onboardingApi.saveBrand(token, {
        three_words: words.map((word) => word.trim()) as [string, string, string],
        colors: noBrandYet ? [] : colors,
        no_brand_yet: noBrandYet,
      });
      setState(next);
      goTo("photos");
    } catch (error) {
      toast.error(messageOf(error));
    } finally {
      setPending(false);
    }
  }

  const logoName = upload?.fileName ?? (logo ? (uploadedName ?? "Tu logo") : null);
  const logoSrc = upload?.previewUrl ?? logo?.url;

  return (
    <WizardStep step="brand" title="Tu marca" onSubmit={submit} pending={pending || uploading}>
      <FieldLabel className="w-full cursor-pointer rounded-lg bg-callout px-3.5 py-2.5 text-callout-foreground">
        <Field orientation="horizontal" className="items-center gap-3">
          <Checkbox
            checked={noBrandYet}
            onCheckedChange={(checked) => setNoBrandYet(checked)}
          />
          <FieldContent>
            <FieldTitle className="text-[15px] font-semibold text-foreground">
              Todavía no tengo logo ni colores
            </FieldTitle>
            <FieldDescription className="text-[13px] text-callout-foreground">
              Te ayudamos a elegirlos por WhatsApp
            </FieldDescription>
          </FieldContent>
        </Field>
      </FieldLabel>

      {!noBrandYet && (
        <>
          <section aria-labelledby="logo-title" className="flex flex-col gap-2">
            <h2 id="logo-title" className="text-sm font-semibold">
              Tu logo <span className="font-normal text-muted-foreground">(opcional)</span>
            </h2>
            <input
              ref={fileInput}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/heic,.heic"
              className="sr-only"
              tabIndex={-1}
              aria-hidden
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) uploadLogo(file);
              }}
            />
            {logoName && logoSrc ? (
              <div className="flex items-center gap-3.5 rounded-lg border bg-card p-3">
                <div className="flex size-18 shrink-0 items-center justify-center overflow-hidden rounded-md bg-muted">
                  {/* eslint-disable-next-line @next/next/no-img-element -- signed Storage URLs and object URLs */}
                  <img src={logoSrc} alt="Tu logo" className="size-full object-contain" />
                </div>
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <p className="truncate text-[15px] font-semibold">{logoName}</p>
                  {upload && !upload.failed && (
                    <Progress value={upload.progress * 100} aria-label="Subiendo logo" />
                  )}
                  {upload?.failed && <p className="text-[13px] text-destructive">No se pudo subir</p>}
                  {!upload && (
                    <p className="flex items-center gap-1 text-[13px] text-primary">
                      <CheckIcon className="size-3.5" aria-hidden />
                      Subido
                    </p>
                  )}
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  size="lg"
                  className="h-11"
                  disabled={uploading}
                  onClick={() => fileInput.current?.click()}
                >
                  {upload?.failed ? "Reintentar" : "Cambiar"}
                </Button>
              </div>
            ) : (
              <Button
                type="button"
                variant="ghost"
                className="h-24 flex-col gap-1.5 border-[1.5px] border-dashed border-input bg-card text-[15px] font-semibold text-primary hover:bg-card hover:text-primary"
                onClick={() => fileInput.current?.click()}
              >
                <ImageUpIcon className="size-6" aria-hidden />
                Subir logo
              </Button>
            )}
          </section>

          <FieldSet data-invalid={!!show(errors.colors)} className="gap-2.5">
            <div className="flex flex-col gap-0.5">
              <FieldLegend variant="label" className="mb-0 font-semibold">
                Tus colores
              </FieldLegend>
              <FieldDescription className="text-[13px]">
                {logo
                  ? "Los sacamos de tu logo. Tocá uno para cambiarlo."
                  : "Subí tu logo y los sacamos de ahí, o agregalos vos."}
              </FieldDescription>
            </div>
            <ul className="flex flex-wrap gap-3.5">
              {colors.map((color, index) => (
                <li key={index} className="relative flex flex-col items-center gap-1.5">
                  <label
                    className="relative block size-14 cursor-pointer rounded-lg shadow-[inset_0_0_0_1px_rgb(31_27_22/0.12)] focus-within:ring-3 focus-within:ring-ring/40"
                    style={{ background: color }}
                  >
                    <span className="sr-only">Cambiar color {color}</span>
                    <input
                      type="color"
                      value={color}
                      className="absolute inset-0 size-full cursor-pointer opacity-0"
                      onChange={(event) =>
                        setColors((list) => list.map((item, i) => (i === index ? event.target.value : item)))
                      }
                    />
                  </label>
                  <span className="font-mono text-xs text-muted-foreground uppercase">{color}</span>
                  {colors.length > 1 && (
                    <button
                      type="button"
                      aria-label={`Quitar color ${color}`}
                      className="absolute -top-2.5 -right-2.5 flex size-7 items-center justify-center rounded-full border bg-card text-muted-foreground shadow-sm"
                      onClick={() => setColors((list) => list.filter((_, i) => i !== index))}
                    >
                      <XIcon className="size-3.5" aria-hidden />
                    </button>
                  )}
                </li>
              ))}
              {colors.length < MAX_COLORS && (
                <li>
                  <button
                    type="button"
                    className="flex flex-col items-center gap-1.5 rounded-lg text-xs text-muted-foreground outline-none focus-visible:ring-3 focus-visible:ring-ring/40"
                    onClick={() => setColors((list) => [...list, NEW_COLOR])}
                  >
                    <span className="flex size-14 items-center justify-center rounded-lg border-[1.5px] border-dashed border-input text-primary">
                      <PlusIcon className="size-5" aria-hidden />
                    </span>
                    Agregar
                  </button>
                </li>
              )}
            </ul>
            <FieldError>{show(errors.colors)}</FieldError>
          </FieldSet>
        </>
      )}

      <FieldSet data-invalid={!!show(errors.words)} className="gap-2.5">
        <FieldLegend variant="label" className="mb-0 font-semibold">
          3 palabras que usarían tus clientes para describirte
        </FieldLegend>
        {words.map((word, index) => (
          <Input
            key={index}
            aria-label={`Palabra ${index + 1}`}
            placeholder={WORD_PLACEHOLDERS[index]}
            value={word}
            onChange={(event) =>
              setWords((list) => list.map((item, i) => (i === index ? event.target.value : item)))
            }
            aria-invalid={!!show(errors.words) && !word.trim()}
          />
        ))}
        <FieldError>{show(errors.words)}</FieldError>
      </FieldSet>
    </WizardStep>
  );
}
