"use client";

import { useState, type ReactNode } from "react";
import { SparklesIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { asOptions, ChoiceChips } from "@/components/onboarding/choice-chips";
import { WizardStep } from "@/components/onboarding/wizard-step";
import { useWizard } from "@/components/onboarding/wizard-context";
import { messageOf, onboardingApi, type EmojiPolicy, type Goal, type Scale } from "@/lib/api";
import { copyFor } from "@/lib/categories";
import { isInstagramConnected } from "@/lib/onboarding";

const GOALS: { value: Goal; label: string }[] = [
  { value: "sales", label: "Más consultas y ventas" },
  { value: "awareness", label: "Que me conozca más gente" },
  { value: "launch", label: "Lanzar algo nuevo" },
  { value: "loyalty", label: "Que vuelvan mis clientes" },
];

const OTHER_AUDIENCE = "Otro";
const DEFAULT_SCALE: Scale = 3;

function isScale(value: unknown): value is Scale {
  return typeof value === "number" && Number.isInteger(value) && value >= 1 && value <= 5;
}

const EMOJI_POLICIES: { value: EmojiPolicy; label: string }[] = [
  { value: "many", label: "Sí, bastantes" },
  { value: "few", label: "Pocos" },
  { value: "none", label: "Ninguno" },
];

export function PreferencesStep() {
  const { token, state, setState, goTo } = useWizard();
  const saved = state.preferences;
  const copy = copyFor(state.business.category);
  const fromInstagram = isInstagramConnected(state);
  const savedOther = saved?.audiences.find((audience) => !copy.audiences.includes(audience)) ?? "";
  const savedTone = saved?.formality != null || saved?.humor != null || saved?.emoji_policy != null;

  const [goal, setGoal] = useState<Goal | null>(saved?.goal ?? null);
  const [audiences, setAudiences] = useState<string[]>(() => [
    ...(saved?.audiences.filter((audience) => copy.audiences.includes(audience)) ?? []),
    ...(savedOther ? [OTHER_AUDIENCE] : []),
  ]);
  const [otherAudience, setOtherAudience] = useState(savedOther);
  const [choosingTone, setChoosingTone] = useState(!fromInstagram || savedTone);
  const [formality, setFormality] = useState<Scale>(saved?.formality ?? DEFAULT_SCALE);
  const [humor, setHumor] = useState<Scale>(saved?.humor ?? DEFAULT_SCALE);
  const [emoji, setEmoji] = useState<EmojiPolicy | null>(saved?.emoji_policy ?? null);
  const [avoid, setAvoid] = useState(saved?.avoid ?? "");
  const [currentOffer, setCurrentOffer] = useState(saved?.current_offer ?? "");
  const [submitted, setSubmitted] = useState(false);
  const [pending, setPending] = useState(false);

  const errors = {
    goal: !goal && "Elegí el que más te importe hoy.",
    emoji: choosingTone && !emoji && "Elegí una opción.",
  };
  const show = (error: string | false) => (submitted ? error : false);

  async function submit() {
    setSubmitted(true);
    if (!goal || errors.emoji) return;

    const chosenAudiences = audiences.filter((audience) => audience !== OTHER_AUDIENCE);
    if (audiences.includes(OTHER_AUDIENCE) && otherAudience.trim()) {
      chosenAudiences.push(otherAudience.trim());
    }

    setPending(true);
    try {
      const next = await onboardingApi.savePreferences(token, {
        goal,
        audiences: chosenAudiences,
        formality: choosingTone ? formality : null,
        humor: choosingTone ? humor : null,
        emoji_policy: choosingTone ? emoji : null,
        posts_per_week: saved?.posts_per_week ?? null,
        avoid: avoid.trim() || null,
        current_offer: currentOffer.trim() || null,
      });
      setState(next);
      goTo("done");
    } catch (error) {
      toast.error(messageOf(error));
    } finally {
      setPending(false);
    }
  }

  return (
    <WizardStep
      step="preferences"
      title="Última: ¿cómo querés que suene?"
      onSubmit={submit}
      pending={pending}
    >
      <Question id="goal" legend="¿Qué querés lograr con tus redes?" error={show(errors.goal)}>
        <ChoiceChips
          aria-labelledby="goal"
          options={GOALS}
          value={goal ? [goal] : []}
          onChange={(value) => setGoal(GOALS.find((option) => option.value === value[0])?.value ?? null)}
          invalid={!!show(errors.goal)}
        />
      </Question>

      <Question
        id="audiences"
        legend={
          <>
            ¿A quién le vendés? <span className="font-normal text-muted-foreground">(podés elegir varios)</span>
          </>
        }
      >
        <ChoiceChips
          aria-labelledby="audiences"
          multiple
          options={asOptions([...copy.audiences, OTHER_AUDIENCE])}
          value={audiences}
          onChange={setAudiences}
        />
        {audiences.includes(OTHER_AUDIENCE) && (
          <Input
            aria-label="¿A quién más le vendés?"
            placeholder="Ej: turistas"
            value={otherAudience}
            onChange={(event) => setOtherAudience(event.target.value)}
          />
        )}
      </Question>

      {choosingTone ? (
        <>
          <Question id="tone" legend="El tono">
            <ToneSlider label="Formal a cercano" start="Formal" end="Cercano" value={formality} onChange={setFormality} />
            <ToneSlider label="Serio a divertido" start="Serio" end="Divertido" value={humor} onChange={setHumor} />
          </Question>

          <Question id="emoji" legend="¿Usamos emojis?" error={show(errors.emoji)}>
            <ChoiceChips
              aria-labelledby="emoji"
              options={EMOJI_POLICIES}
              value={emoji ? [emoji] : []}
              onChange={(value) => setEmoji(EMOJI_POLICIES.find((option) => option.value === value[0])?.value ?? null)}
              invalid={!!show(errors.emoji)}
            />
          </Question>
        </>
      ) : (
        <div className="flex items-start gap-3.5 rounded-[22px] bg-card p-4 shadow-bubble">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary">
            <SparklesIcon className="size-5" aria-hidden />
          </span>
          <div className="flex flex-col items-start gap-1">
            <p className="text-base leading-snug">
              <strong>El tono lo aprendo de tu Instagram:</strong> cómo escribís, si usás emojis, qué le gusta a tu
              gente.
            </p>
            <Button
              type="button"
              variant="link"
              className="h-auto p-0 text-[15px] font-bold underline underline-offset-3"
              onClick={() => setChoosingTone(true)}
            >
              Prefiero elegirlo yo
            </Button>
          </div>
        </div>
      )}

      <Question id="extras" legend="Por las dudas">
        <Field>
          <FieldLabel htmlFor="avoid" className="font-normal">
            <span>
              ¿Hay algo que NO quieras que diga o muestre?{" "}
              <span className="text-muted-foreground">(opcional)</span>
            </span>
          </FieldLabel>
          <Input
            id="avoid"
            placeholder="Ej: no hablar de precios"
            value={avoid}
            onChange={(event) => setAvoid(event.target.value)}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="current-offer" className="font-normal">
            <span>
              ¿Tenés alguna promo o novedad ahora? <span className="text-muted-foreground">(opcional)</span>
            </span>
          </FieldLabel>
          <Input
            id="current-offer"
            placeholder={`Ej: ${copy.offer}`}
            value={currentOffer}
            onChange={(event) => setCurrentOffer(event.target.value)}
          />
        </Field>
      </Question>
    </WizardStep>
  );
}

function Question({
  id,
  legend,
  error,
  children,
}: {
  id: string;
  legend: ReactNode;
  error?: string | false;
  children: ReactNode;
}) {
  return (
    <FieldSet data-invalid={!!error} className="gap-3">
      <FieldLegend id={id} variant="label" className="float-left mb-0 w-full text-[15px] font-bold">
        {legend}
      </FieldLegend>
      {children}
      <FieldError>{error}</FieldError>
    </FieldSet>
  );
}

function ToneSlider({
  label,
  start,
  end,
  value,
  onChange,
}: {
  label: string;
  start: string;
  end: string;
  value: Scale;
  onChange: (value: Scale) => void;
}) {
  return (
    <div className="flex flex-col gap-2 pt-2">
      <Slider
        thumbLabel={label}
        min={1}
        max={5}
        step={1}
        value={value}
        onValueChange={(next) => {
          if (isScale(next)) onChange(next);
        }}
      />
      <div className="flex justify-between text-[13px] text-muted-foreground" aria-hidden>
        <span>{start}</span>
        <span>{end}</span>
      </div>
    </div>
  );
}
