"use client";

import { useState, type ReactNode } from "react";
import { CheckIcon } from "lucide-react";
import { toast } from "sonner";
import { Field, FieldError, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { WizardStep } from "@/components/onboarding/wizard-step";
import { useWizard } from "@/components/onboarding/wizard-context";
import {
  messageOf,
  onboardingApi,
  type EmojiPolicy,
  type Goal,
  type PostsPerWeek,
  type Scale,
} from "@/lib/api";

const GOALS: { value: Goal; label: string }[] = [
  { value: "sales", label: "Más consultas y ventas" },
  { value: "awareness", label: "Que me conozca más gente" },
  { value: "launch", label: "Lanzar algo nuevo" },
  { value: "loyalty", label: "Fidelizar a mis clientes" },
];

const AUDIENCES = ["Familias", "Parejas jóvenes", "Empresas/oficinas", "Arquitectos/decoradores"];
const OTHER_AUDIENCE = "Otro";

const POSTS_PER_WEEK: PostsPerWeek[] = [2, 3, 5];

const EMOJI_POLICIES: { value: EmojiPolicy; label: string }[] = [
  { value: "many", label: "Sí, bastantes" },
  { value: "few", label: "Pocos" },
  { value: "none", label: "Ninguno" },
];

export function PreferencesStep() {
  const { token, state, setState, goTo } = useWizard();
  const saved = state.preferences;
  const savedOther = saved?.audiences.find((audience) => !AUDIENCES.includes(audience)) ?? "";

  const [goal, setGoal] = useState<Goal | null>(saved?.goal ?? null);
  const [audiences, setAudiences] = useState<string[]>(() => [
    ...(saved?.audiences.filter((audience) => AUDIENCES.includes(audience)) ?? []),
    ...(savedOther ? [OTHER_AUDIENCE] : []),
  ]);
  const [otherAudience, setOtherAudience] = useState(savedOther);
  const [formality, setFormality] = useState<Scale>(saved?.formality ?? 3);
  const [humor, setHumor] = useState<Scale>(saved?.humor ?? 3);
  const [postsPerWeek, setPostsPerWeek] = useState<PostsPerWeek | null>(saved?.posts_per_week ?? 3);
  const [emoji, setEmoji] = useState<EmojiPolicy | null>(saved?.emoji_policy ?? null);
  const [avoid, setAvoid] = useState(saved?.avoid ?? "");
  const [currentOffer, setCurrentOffer] = useState(saved?.current_offer ?? "");
  const [submitted, setSubmitted] = useState(false);
  const [pending, setPending] = useState(false);

  const errors = {
    goal: !goal && "Elegí uno.",
    postsPerWeek: !postsPerWeek && "Elegí cuántas.",
    emoji: !emoji && "Elegí una opción.",
  };
  const show = (error: string | false) => (submitted ? error : false);

  async function submit() {
    setSubmitted(true);
    if (!goal || !postsPerWeek || !emoji) return;

    const chosenAudiences = audiences.filter((audience) => audience !== OTHER_AUDIENCE);
    if (audiences.includes(OTHER_AUDIENCE) && otherAudience.trim()) {
      chosenAudiences.push(otherAudience.trim());
    }

    setPending(true);
    try {
      const next = await onboardingApi.savePreferences(token, {
        goal,
        audiences: chosenAudiences,
        formality,
        humor,
        posts_per_week: postsPerWeek,
        emoji_policy: emoji,
        avoid: avoid.trim() || null,
        current_offer: currentOffer.trim() || null,
      });
      setState(next);
      goTo("instagram");
    } catch (error) {
      toast.error(messageOf(error));
    } finally {
      setPending(false);
    }
  }

  return (
    <WizardStep step="preferences" title="¿Cómo querés que suene?" onSubmit={submit} pending={pending}>
      <Question legend="¿Qué querés lograr con tus redes?" error={show(errors.goal)}>
        <ToggleGroup
          variant="chip"
          size="lg"
          className="flex-wrap"
          value={goal ? [goal] : []}
          onValueChange={(value: string[]) => value[0] && setGoal(value[0] as Goal)}
        >
          {GOALS.map((option) => (
            <Chip key={option.value} value={option.value} pressed={goal === option.value}>
              {option.label}
            </Chip>
          ))}
        </ToggleGroup>
      </Question>

      <Question
        legend={
          <>
            ¿A quién le vendés?{" "}
            <span className="font-normal text-muted-foreground">(podés elegir varios)</span>
          </>
        }
      >
        <ToggleGroup
          multiple
          variant="chip"
          size="lg"
          className="flex-wrap"
          value={audiences}
          onValueChange={(value: string[]) => setAudiences(value)}
        >
          {[...AUDIENCES, OTHER_AUDIENCE].map((audience) => (
            <Chip key={audience} value={audience} pressed={audiences.includes(audience)}>
              {audience}
            </Chip>
          ))}
        </ToggleGroup>
        {audiences.includes(OTHER_AUDIENCE) && (
          <Input
            aria-label="¿A quién más le vendés?"
            placeholder="Ej: turistas"
            value={otherAudience}
            onChange={(event) => setOtherAudience(event.target.value)}
          />
        )}
      </Question>

      <Question legend="El tono">
        <ToneSlider
          label="Formal a cercano"
          start="Formal"
          end="Cercano"
          value={formality}
          onChange={setFormality}
        />
        <ToneSlider
          label="Serio a divertido"
          start="Serio"
          end="Divertido"
          value={humor}
          onChange={setHumor}
        />
      </Question>

      <Question legend="¿Cuántas publicaciones por semana?" error={show(errors.postsPerWeek)}>
        <ToggleGroup
          variant="segment"
          size="xl"
          spacing={1}
          className="w-full rounded-lg bg-muted p-1"
          value={postsPerWeek ? [String(postsPerWeek)] : []}
          onValueChange={(value: string[]) =>
            value[0] && setPostsPerWeek(Number(value[0]) as PostsPerWeek)
          }
        >
          {POSTS_PER_WEEK.map((count) => (
            <ToggleGroupItem key={count} value={String(count)}>
              {count}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </Question>

      <Question legend="¿Usamos emojis?" error={show(errors.emoji)}>
        <ToggleGroup
          variant="chip"
          size="lg"
          className="flex-wrap"
          value={emoji ? [emoji] : []}
          onValueChange={(value: string[]) => value[0] && setEmoji(value[0] as EmojiPolicy)}
        >
          {EMOJI_POLICIES.map((option) => (
            <Chip key={option.value} value={option.value} pressed={emoji === option.value}>
              {option.label}
            </Chip>
          ))}
        </ToggleGroup>
      </Question>

      <Question legend="Para terminar">
        <Field>
          <FieldLabel htmlFor="avoid">
            <span>
              ¿Hay algo que NO quieras que digamos o mostremos?{" "}
              <span className="font-normal text-muted-foreground">(opcional)</span>
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
          <FieldLabel htmlFor="current-offer">
            <span>
              ¿Tenés alguna promo o novedad ahora?{" "}
              <span className="font-normal text-muted-foreground">(opcional)</span>
            </span>
          </FieldLabel>
          <Input
            id="current-offer"
            placeholder="Ej: 15% en sillas hasta fin de mes"
            value={currentOffer}
            onChange={(event) => setCurrentOffer(event.target.value)}
          />
        </Field>
      </Question>
    </WizardStep>
  );
}

function Question({
  legend,
  error,
  children,
}: {
  legend: ReactNode;
  error?: string | false;
  children: ReactNode;
}) {
  return (
    <FieldSet
      data-invalid={!!error}
      className="gap-3 rounded-lg border bg-card p-3.5 data-[invalid=true]:border-destructive"
    >
      <FieldLegend variant="label" className="float-left mb-0 w-full text-[15px] font-semibold">
        {legend}
      </FieldLegend>
      {children}
      <FieldError>{error}</FieldError>
    </FieldSet>
  );
}

function Chip({ value, pressed, children }: { value: string; pressed: boolean; children: ReactNode }) {
  return (
    <ToggleGroupItem value={value}>
      {pressed && <CheckIcon data-icon="inline-start" className="stroke-3" />}
      {children}
    </ToggleGroupItem>
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
        onValueChange={(next) => onChange(next as Scale)}
      />
      <div className="flex justify-between text-[12.5px] text-muted-foreground" aria-hidden>
        <span>{start}</span>
        <span>{end}</span>
      </div>
    </div>
  );
}
