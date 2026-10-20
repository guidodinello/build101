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
import { asOptions, ChoiceChips } from "@/components/onboarding/choice-chips";
import { PostPreview } from "@/components/onboarding/post-preview";
import { WizardStep } from "@/components/onboarding/wizard-step";
import { useWizard } from "@/components/onboarding/wizard-context";
import { messageOf, onboardingApi, type OnboardingState } from "@/lib/api";
import { copyFor } from "@/lib/categories";
import { currentLogo, MAX_BRAND_WORDS, ownPhotos, readyPhotos } from "@/lib/onboarding";
import { uploadAsset, validatePhoto } from "@/lib/upload";

const MAX_COLORS = 5;
const NEW_COLORS = ["#c89b6d", "#4b5d3a", "#e9dcc6", "#6b3e26", "#1f3a5f"] as const;

type LogoUpload = {
  fileName: string;
  previewUrl: string;
  progress: number;
  failed: boolean;
};

function previewPhoto(state: OnboardingState) {
  const own = ownPhotos(state);
  const photo =
    own.find((asset) => asset.product_ids.length > 0) ?? own[0] ?? readyPhotos(state)[0];
  return photo ? (photo.thumbnail_url ?? photo.url) : null;
}

export function BrandStep() {
  const { token, state, setState, upsertAsset, goTo } = useWizard();
  const logo = currentLogo(state);
  const suggestions = copyFor(state.business.category).words;
  const [noBrandYet, setNoBrandYet] = useState(
    !logo && state.brand.colors.length === 0 && state.brand.three_words.length > 0,
  );
  const [colors, setColors] = useState(() =>
    state.brand.colors.length > 0 ? state.brand.colors : (logo?.palette ?? []),
  );
  const [words, setWords] = useState<string[]>(state.brand.three_words);
  const [customWord, setCustomWord] = useState("");
  const [upload, setUpload] = useState<LogoUpload | null>(null);
  const [uploadedName, setUploadedName] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [pending, setPending] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const uploading = !!upload && !upload.failed;
  const wordOptions = [...suggestions, ...words.filter((word) => !suggestions.includes(word))];
  const errors = {
    colors: !noBrandYet && colors.length === 0 && "Sumá al menos un color, o subí tu logo.",
    words: words.length === 0 && "Elegí al menos una.",
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

  function addColor() {
    const next = NEW_COLORS.find((color) => !colors.includes(color)) ?? NEW_COLORS[0];
    setColors((list) => [...list, next]);
  }

  function addCustomWord() {
    const word = customWord.trim();
    if (!word) return;
    if (words.length >= MAX_BRAND_WORDS) {
      toast(`Elegí hasta ${MAX_BRAND_WORDS}. Sacá una para sumar otra.`);
      return;
    }
    if (!words.some((item) => item.toLowerCase() === word.toLowerCase())) {
      setWords((list) => [...list, word]);
    }
    setCustomWord("");
  }

  async function submit() {
    setSubmitted(true);
    if (errors.colors || errors.words || uploading) return;

    setPending(true);
    try {
      const next = await onboardingApi.saveBrand(token, {
        three_words: words,
        colors: noBrandYet ? [] : colors,
        no_brand_yet: noBrandYet,
      });
      setState(next);
      goTo("preferences");
    } catch (error) {
      toast.error(messageOf(error));
    } finally {
      setPending(false);
    }
  }

  const logoName = upload?.fileName ?? (logo ? (uploadedName ?? "Tu logo") : null);
  const logoSrc = upload?.previewUrl ?? logo?.url;

  return (
    <WizardStep
      step="brand"
      title="Así se vería tu marca"
      subtitle="Tocá los colores y mirá cómo cambia."
      onSubmit={submit}
      pending={pending || uploading}
    >
      <PostPreview
        name={state.business.name ?? "Tu negocio"}
        location={state.business.location}
        caption={state.business.one_liner}
        photoUrl={previewPhoto(state)}
        logoUrl={noBrandYet ? null : (logoSrc ?? null)}
        colors={noBrandYet ? [] : colors}
      />

      <FieldLabel className="w-full cursor-pointer rounded-[18px] bg-card px-3.5 py-3 shadow-[0_0_0_1px_var(--border)]">
        <Field orientation="horizontal" className="items-center gap-3">
          <Checkbox checked={noBrandYet} onCheckedChange={(checked) => setNoBrandYet(checked)} />
          <FieldContent>
            <FieldTitle className="text-[15px] font-semibold text-foreground">
              Todavía no tengo logo ni colores
            </FieldTitle>
            <FieldDescription className="text-[13px]">
              Uso colores neutros. Los cambiamos cuando quieras por WhatsApp.
            </FieldDescription>
          </FieldContent>
        </Field>
      </FieldLabel>

      {!noBrandYet && (
        <>
          <section aria-labelledby="logo-title" className="flex flex-col gap-2.5">
            <h2 id="logo-title" className="text-[15px] font-bold">
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
              <div className="flex items-center gap-3.5 rounded-[18px] bg-card p-3 shadow-[0_0_0_1px_var(--border)]">
                <div className="flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-md bg-muted">
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
                    <p className="flex items-center gap-1 text-[13px] font-medium text-primary">
                      <CheckIcon className="size-3.5" aria-hidden />
                      Subido
                    </p>
                  )}
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  size="lg"
                  className="h-11 rounded-full"
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
                className="h-20 gap-2.5 rounded-[18px] border-[1.5px] border-dashed border-input bg-card text-base font-bold text-primary hover:bg-card hover:text-primary"
                onClick={() => fileInput.current?.click()}
              >
                <ImageUpIcon className="size-6" aria-hidden />
                Subir logo
              </Button>
            )}
          </section>

          <FieldSet data-invalid={!!show(errors.colors)} className="gap-3">
            <div className="flex flex-col gap-0.5">
              <FieldLegend variant="label" className="mb-0 text-[15px] font-bold">
                Tus colores
              </FieldLegend>
              <FieldDescription className="text-sm">
                {logo
                  ? "Los saqué de tu logo. Tocá uno para cambiarlo."
                  : "Subí tu logo y los saco de ahí, o agregalos vos."}
              </FieldDescription>
            </div>
            <ul className="flex flex-wrap gap-3.5">
              {colors.map((color, index) => (
                <li key={`${index}-${color}`} className="relative flex flex-col items-center gap-1.5">
                  <label
                    className="relative block size-14 cursor-pointer rounded-full shadow-[inset_0_0_0_1px_rgb(14_42_32/0.12)] focus-within:ring-3 focus-within:ring-primary/40"
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
                      className="absolute -top-2 -right-2 flex size-7 items-center justify-center rounded-full bg-card text-muted-foreground shadow-float"
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
                    className="flex flex-col items-center gap-1.5 rounded-full text-xs font-medium text-muted-foreground outline-none focus-visible:ring-3 focus-visible:ring-primary/40"
                    onClick={addColor}
                  >
                    <span className="flex size-14 items-center justify-center rounded-full border-[1.5px] border-dashed border-input bg-card text-primary">
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

      <FieldSet data-invalid={!!show(errors.words)} className="gap-3">
        <div className="flex flex-col gap-0.5">
          <FieldLegend id="words-label" variant="label" className="mb-0 text-[15px] font-bold">
            ¿Cómo te describirían tus clientes?
          </FieldLegend>
          <FieldDescription className="text-sm">Elegí hasta {MAX_BRAND_WORDS}.</FieldDescription>
        </div>
        <ChoiceChips
          aria-labelledby="words-label"
          multiple
          max={MAX_BRAND_WORDS}
          options={asOptions(wordOptions)}
          value={words}
          onChange={setWords}
          invalid={!!show(errors.words)}
        />
        <div className="flex gap-2">
          <Input
            aria-label="Otra palabra"
            placeholder="Otra palabra"
            value={customWord}
            onChange={(event) => setCustomWord(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== "Enter") return;
              event.preventDefault();
              addCustomWord();
            }}
          />
          <Button
            type="button"
            variant="secondary"
            size="lg"
            className="h-12 rounded-full px-5"
            disabled={!customWord.trim()}
            onClick={addCustomWord}
          >
            Sumar
          </Button>
        </div>
        <FieldError>{show(errors.words)}</FieldError>
      </FieldSet>
    </WizardStep>
  );
}
