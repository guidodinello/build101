"use client";

import { useCallback, useState } from "react";
import { PlusIcon, XIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ProductPhotos } from "@/components/onboarding/product-photos";
import { WizardStep } from "@/components/onboarding/wizard-step";
import { useWizard } from "@/components/onboarding/wizard-context";
import { messageOf, onboardingApi, type OnboardingState, type Product } from "@/lib/api";
import { MAX_PHOTOS, MAX_PRODUCTS, readyPhotos } from "@/lib/onboarding";

type ProductDraft = {
  key: number;
  id?: string;
  name: string;
  description: string;
  price: string;
  assetIds: string[];
};

let nextKey = 0;

function draftOf(state: OnboardingState, product?: Product): ProductDraft {
  return {
    key: nextKey++,
    id: product?.id,
    name: product?.name ?? "",
    description: product?.description ?? "",
    price: product?.price ?? "",
    assetIds: product
      ? readyPhotos(state)
          .filter((asset) => asset.product_ids.includes(product.id))
          .map((asset) => asset.id)
      : [],
  };
}

const isBlank = (draft: ProductDraft) =>
  !draft.name.trim() && !draft.description.trim() && !draft.price.trim() && draft.assetIds.length === 0;

export function ProductsStep() {
  const { token, state, setState, goTo, photoUploads } = useWizard();
  const [drafts, setDrafts] = useState<ProductDraft[]>(() => {
    const saved = state.products
      .filter((product) => !product.archived)
      .sort((a, b) => a.position - b.position)
      .map((product) => draftOf(state, product));
    return saved.length > 0 ? saved : [draftOf(state)];
  });
  const [submitted, setSubmitted] = useState(false);
  const [pending, setPending] = useState(false);
  const [uploading, setUploading] = useState<Record<number, number>>({});

  const uploadingCount = Object.values(uploading).reduce((sum, count) => sum + count, 0);
  const photoRoom =
    MAX_PHOTOS - readyPhotos(state).length - uploadingCount - photoUploads.inFlight;

  const setUploadingOf = useCallback((key: number, count: number) => {
    setUploading((current) => (current[key] === count ? current : { ...current, [key]: count }));
  }, []);

  const filled = drafts.filter((draft) => !isBlank(draft));
  const errorsOf = (draft: ProductDraft) => {
    if (!submitted || (isBlank(draft) && filled.length > 0)) return { name: false, description: false };
    return {
      name: !draft.name.trim() && "Ponele un nombre.",
      description: !draft.description.trim() && "Contalo en pocas palabras.",
    };
  };

  function update(key: number, changes: Partial<ProductDraft>) {
    setDrafts((list) => list.map((draft) => (draft.key === key ? { ...draft, ...changes } : draft)));
  }

  function updateAssetIds(key: number, change: (current: string[]) => string[]) {
    setDrafts((list) =>
      list.map((draft) => (draft.key === key ? { ...draft, assetIds: change(draft.assetIds) } : draft)),
    );
  }

  function removeDraft(draft: ProductDraft) {
    setDrafts((list) => list.filter((item) => item.key !== draft.key));
    setUploading((current) => {
      const next = { ...current };
      delete next[draft.key];
      return next;
    });
    if (draft.assetIds.length === 0) return;
    const removed = new Set(draft.assetIds);
    setState((current) => ({
      ...current,
      assets: current.assets.filter((asset) => !removed.has(asset.id)),
    }));
    for (const id of removed) onboardingApi.deleteAsset(token, id).catch(() => undefined);
  }

  async function submit() {
    setSubmitted(true);
    const invalid =
      filled.length === 0 || filled.some((draft) => !draft.name.trim() || !draft.description.trim());
    if (invalid) return;
    if (uploadingCount > 0) {
      toast("Esperá un toque que terminen de subir las fotos.");
      return;
    }

    setPending(true);
    try {
      const next = await onboardingApi.saveProducts(
        token,
        filled.map((draft) => ({
          id: draft.id,
          name: draft.name.trim(),
          description: draft.description.trim(),
          price: draft.price.trim() || undefined,
          asset_ids: draft.assetIds,
        })),
      );
      setState(next);
      goTo("brand");
    } catch (error) {
      toast.error(messageOf(error));
    } finally {
      setPending(false);
    }
  }

  return (
    <WizardStep
      step="products"
      title="¿Qué es lo que más vendés?"
      subtitle="Hasta 5. Los que más te importa vender."
      onSubmit={submit}
      pending={pending}
    >
      {drafts.map((draft, index) => {
        const errors = errorsOf(draft);
        const number = index + 1;
        return (
          <section
            key={draft.key}
            aria-labelledby={`product-${draft.key}-title`}
            className="flex flex-col gap-3 rounded-lg border bg-card p-3.5"
          >
            <div className="-my-1.5 flex items-center justify-between">
              <h2
                id={`product-${draft.key}-title`}
                className="text-[13px] font-bold tracking-wide text-primary uppercase"
              >
                Producto {number}
              </h2>
              {drafts.length > 1 && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-lg"
                  className="-mr-2.5 text-muted-foreground"
                  aria-label={`Quitar producto ${number}`}
                  onClick={() => removeDraft(draft)}
                >
                  <XIcon />
                </Button>
              )}
            </div>
            <FieldGroup className="gap-3">
              <Field data-invalid={!!errors.name}>
                <FieldLabel htmlFor={`product-${draft.key}-name`}>Nombre</FieldLabel>
                <Input
                  id={`product-${draft.key}-name`}
                  placeholder="Ej: Mesa Nórdica"
                  value={draft.name}
                  onChange={(event) => update(draft.key, { name: event.target.value })}
                  aria-invalid={!!errors.name}
                />
                <FieldError>{errors.name}</FieldError>
              </Field>
              <Field data-invalid={!!errors.description}>
                <FieldLabel htmlFor={`product-${draft.key}-description`}>En pocas palabras</FieldLabel>
                <Input
                  id={`product-${draft.key}-description`}
                  placeholder="Ej: hecha a mano, en roble macizo"
                  value={draft.description}
                  onChange={(event) => update(draft.key, { description: event.target.value })}
                  aria-invalid={!!errors.description}
                />
                <FieldError>{errors.description}</FieldError>
              </Field>
              <Field>
                <FieldLabel htmlFor={`product-${draft.key}-price`}>
                  Precio <span className="font-normal text-muted-foreground">(opcional)</span>
                </FieldLabel>
                <Input
                  id={`product-${draft.key}-price`}
                  inputMode="text"
                  placeholder="Ej: $ 18.500"
                  value={draft.price}
                  onChange={(event) => update(draft.key, { price: event.target.value })}
                />
              </Field>
            </FieldGroup>
            <ProductPhotos
              productLabel={draft.name.trim() || `producto ${number}`}
              assetIds={draft.assetIds}
              room={photoRoom}
              onChange={(change) => updateAssetIds(draft.key, change)}
              onUploadingChange={(count) => setUploadingOf(draft.key, count)}
            />
          </section>
        );
      })}

      {drafts.length < MAX_PRODUCTS && (
        <Button
          type="button"
          variant="ghost"
          size="lg"
          className="h-13 border-[1.5px] border-dashed border-input text-primary hover:bg-card hover:text-primary"
          onClick={() => setDrafts((list) => [...list, draftOf(state)])}
        >
          <PlusIcon data-icon="inline-start" />
          Agregar otro
        </Button>
      )}
    </WizardStep>
  );
}
