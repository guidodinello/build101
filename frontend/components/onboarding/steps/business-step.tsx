"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { WizardStep } from "@/components/onboarding/wizard-step";
import { useWizard } from "@/components/onboarding/wizard-context";
import { messageOf, onboardingApi } from "@/lib/api";

const CATEGORIES = ["Muebles y deco", "Gastronomía", "Indumentaria", "Belleza", "Servicios", "Otro"];
const ONE_LINER_MAX = 120;

export function BusinessStep() {
  const { token, state, setState, goTo } = useWizard();
  const { business } = state;
  const [name, setName] = useState(business.name ?? "");
  const [category, setCategory] = useState<string | null>(business.category);
  const [oneLiner, setOneLiner] = useState(business.one_liner ?? "");
  const [location, setLocation] = useState(business.location ?? "");
  const [instagram, setInstagram] = useState(business.instagram_handle ?? "");
  const [submitted, setSubmitted] = useState(false);
  const [pending, setPending] = useState(false);

  const errors = {
    name: !name.trim() && "Contanos cómo se llama tu negocio.",
    category: !category && "Elegí un rubro.",
    oneLiner: !oneLiner.trim() && "Contalo en una frase.",
    location: !location.trim() && "Contanos dónde están.",
  };
  const show = (error: string | false) => (submitted ? error : false);

  async function submit() {
    setSubmitted(true);
    if (Object.values(errors).some(Boolean) || !category) return;

    setPending(true);
    try {
      const handle = instagram.trim().replace(/^@+/, "");
      const next = await onboardingApi.saveBusiness(token, {
        name: name.trim(),
        category,
        one_liner: oneLiner.trim(),
        location: location.trim(),
        instagram_handle: handle || undefined,
      });
      setState(next);
      goTo("products");
    } catch (error) {
      toast.error(messageOf(error));
    } finally {
      setPending(false);
    }
  }

  return (
    <WizardStep step="business" title="Contanos de tu negocio" onSubmit={submit} pending={pending}>
      <FieldGroup className="gap-4">
        <Field data-invalid={!!show(errors.name)}>
          <FieldLabel htmlFor="name">¿Cómo se llama?</FieldLabel>
          <Input
            id="name"
            autoComplete="organization"
            value={name}
            onChange={(event) => setName(event.target.value)}
            aria-invalid={!!show(errors.name)}
          />
          <FieldError>{show(errors.name)}</FieldError>
        </Field>

        <Field data-invalid={!!show(errors.category)}>
          <FieldLabel htmlFor="category">¿De qué rubro es?</FieldLabel>
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger id="category" aria-invalid={!!show(errors.category)}>
              <SelectValue placeholder="Elegí uno" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {CATEGORIES.map((option) => (
                  <SelectItem key={option} value={option}>
                    {option}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          <FieldError>{show(errors.category)}</FieldError>
        </Field>

        <Field data-invalid={!!show(errors.oneLiner)}>
          <FieldLabel htmlFor="one-liner">Contalo en una frase</FieldLabel>
          <Textarea
            id="one-liner"
            rows={2}
            className="resize-none"
            maxLength={ONE_LINER_MAX}
            placeholder="Ej: Muebles de madera maciza hechos a mano en Montevideo"
            value={oneLiner}
            onChange={(event) => setOneLiner(event.target.value)}
            aria-invalid={!!show(errors.oneLiner)}
          />
          <div className="flex justify-between gap-2">
            <FieldError>{show(errors.oneLiner)}</FieldError>
            <FieldDescription className="ml-auto text-[12.5px] tabular-nums">
              {oneLiner.length}/{ONE_LINER_MAX}
            </FieldDescription>
          </div>
        </Field>

        <Field data-invalid={!!show(errors.location)}>
          <FieldLabel htmlFor="location">¿Dónde están?</FieldLabel>
          <Input
            id="location"
            autoComplete="address-level2"
            placeholder="Ej: Montevideo"
            value={location}
            onChange={(event) => setLocation(event.target.value)}
            aria-invalid={!!show(errors.location)}
          />
          <FieldError>{show(errors.location)}</FieldError>
        </Field>

        <Field>
          <FieldLabel htmlFor="instagram">
            Instagram <span className="font-normal text-muted-foreground">(opcional)</span>
          </FieldLabel>
          <Input
            id="instagram"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            placeholder="@tunegocio"
            value={instagram}
            onChange={(event) => setInstagram(event.target.value)}
          />
        </Field>
      </FieldGroup>
    </WizardStep>
  );
}
