"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { asOptions, ChoiceChips } from "@/components/onboarding/choice-chips";
import { WizardStep } from "@/components/onboarding/wizard-step";
import { useWizard } from "@/components/onboarding/wizard-context";
import { messageOf, onboardingApi } from "@/lib/api";
import { CATEGORIES, copyFor, isListedCategory, OTHER_CATEGORY } from "@/lib/categories";
import { isInstagramConnected } from "@/lib/onboarding";

const ONE_LINER_MAX = 120;

export function BusinessStep() {
  const { token, state, setState, goTo } = useWizard();
  const { business } = state;
  const savedCategory = business.category;
  const [name, setName] = useState(business.name ?? "");
  const [category, setCategory] = useState<string | null>(
    savedCategory && !isListedCategory(savedCategory) ? OTHER_CATEGORY : savedCategory,
  );
  const [otherCategory, setOtherCategory] = useState(
    savedCategory && !isListedCategory(savedCategory) ? savedCategory : "",
  );
  const [oneLiner, setOneLiner] = useState(business.one_liner ?? "");
  const [location, setLocation] = useState(business.location ?? "");
  const [submitted, setSubmitted] = useState(false);
  const [pending, setPending] = useState(false);

  const chosenCategory = category === OTHER_CATEGORY ? otherCategory.trim() : category;
  const errors = {
    name: !name.trim() && "Escribí el nombre de tu negocio.",
    category: !category && "Elegí el que más se parezca.",
    otherCategory: category === OTHER_CATEGORY && !otherCategory.trim() && "Contame de qué rubro es.",
    oneLiner: !oneLiner.trim() && "Escribí una frase corta, aunque sea simple.",
  };
  const show = (error: string | false) => (submitted ? error : false);

  async function submit() {
    setSubmitted(true);
    if (Object.values(errors).some(Boolean) || !chosenCategory) return;

    setPending(true);
    try {
      const next = await onboardingApi.saveBusiness(token, {
        name: name.trim(),
        category: chosenCategory,
        one_liner: oneLiner.trim(),
        location: location.trim() || undefined,
      });
      setState(next);
      goTo(isInstagramConnected(next) ? "products" : "instagram");
    } catch (error) {
      toast.error(messageOf(error));
    } finally {
      setPending(false);
    }
  }

  return (
    <WizardStep
      step="business"
      title="Contame de tu negocio"
      subtitle="Son 5 minutos. Con esto armo posts que suenen a vos."
      onSubmit={submit}
      pending={pending}
    >
      <FieldGroup className="gap-6">
        <Field data-invalid={!!show(errors.name)}>
          <FieldLabel htmlFor="name" className="text-[15px] font-bold">
            ¿Cómo se llama?
          </FieldLabel>
          <Input
            id="name"
            autoComplete="organization"
            value={name}
            onChange={(event) => setName(event.target.value)}
            aria-invalid={!!show(errors.name)}
          />
          <FieldError>{show(errors.name)}</FieldError>
        </Field>

        <Field data-invalid={!!show(errors.category || errors.otherCategory)}>
          <FieldLabel id="category-label" className="text-[15px] font-bold">
            ¿De qué rubro es?
          </FieldLabel>
          <ChoiceChips
            aria-labelledby="category-label"
            options={asOptions(CATEGORIES)}
            value={category ? [category] : []}
            onChange={(value) => setCategory(value[0] ?? null)}
            invalid={!!show(errors.category)}
          />
          {category === OTHER_CATEGORY && (
            <Input
              aria-label="¿Qué rubro?"
              placeholder="Ej: librería, veterinaria, regalos"
              value={otherCategory}
              onChange={(event) => setOtherCategory(event.target.value)}
              aria-invalid={!!show(errors.otherCategory)}
            />
          )}
          <FieldError>{show(errors.category || errors.otherCategory)}</FieldError>
        </Field>

        <Field data-invalid={!!show(errors.oneLiner)}>
          <FieldLabel htmlFor="one-liner" className="text-[15px] font-bold">
            ¿Qué hacés, en una frase?
          </FieldLabel>
          <Textarea
            id="one-liner"
            rows={2}
            className="resize-none"
            maxLength={ONE_LINER_MAX}
            placeholder={`Ej: ${copyFor(chosenCategory).oneLiner}`}
            value={oneLiner}
            onChange={(event) => setOneLiner(event.target.value)}
            aria-invalid={!!show(errors.oneLiner)}
          />
          <div className="flex justify-between gap-2">
            <FieldError>{show(errors.oneLiner)}</FieldError>
            <FieldDescription className="ml-auto text-[13px] tabular-nums">
              {oneLiner.length}/{ONE_LINER_MAX}
            </FieldDescription>
          </div>
        </Field>

        <Field>
          <FieldLabel htmlFor="location" className="text-[15px] font-bold">
            ¿Dónde están? <span className="font-normal text-muted-foreground">(opcional)</span>
          </FieldLabel>
          <Input
            id="location"
            autoComplete="address-level2"
            placeholder="Ej: Montevideo"
            value={location}
            onChange={(event) => setLocation(event.target.value)}
          />
        </Field>
      </FieldGroup>
    </WizardStep>
  );
}
