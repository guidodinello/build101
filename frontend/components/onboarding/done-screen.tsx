"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { CheckIcon, RotateCwIcon } from "lucide-react";
import { Bubble, Label } from "@/components/landing/chat";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { ScreenLayout } from "@/components/onboarding/screen-layout";
import { WhatsAppButton } from "@/components/onboarding/whatsapp-link";
import { useWizard } from "@/components/onboarding/wizard-context";
import { ApiError, messageOf, onboardingApi } from "@/lib/api";
import {
  atHandle,
  currentLogo,
  instagramPhotos,
  isInstagramConnected,
  readyPhotos,
  resumeStep,
} from "@/lib/onboarding";

type Submission = { status: "saving" } | { status: "done" } | { status: "failed"; error: unknown };

export function DoneScreen() {
  const { token, state, setState, goTo } = useWizard();
  const [submission, setSubmission] = useState<Submission>(() =>
    state.completed ? { status: "done" } : { status: "saving" },
  );
  const sent = useRef(false);

  const send = useCallback(() => {
    onboardingApi.complete(token).then(
      () => {
        setSubmission({ status: "done" });
        setState((current) => ({ ...current, completed: true }));
      },
      (error: unknown) => setSubmission({ status: "failed", error }),
    );
  }, [token, setState]);

  useEffect(() => {
    if (state.completed || sent.current) return;
    sent.current = true;
    send();
  }, [state.completed, send]);

  function retry() {
    setSubmission({ status: "saving" });
    send();
  }

  if (submission.status === "saving") {
    return (
      <ScreenLayout
        title="Un segundo…"
        subtitle={
          <span className="flex items-center gap-2">
            <Spinner className="size-4.5" aria-label="Guardando" />
            Estoy guardando todo.
          </span>
        }
      />
    );
  }

  if (submission.status === "failed") {
    const missingData = submission.error instanceof ApiError && submission.error.status === 422;
    return (
      <ScreenLayout
        title="Me falta algo"
        footer={
          missingData ? (
            <Button variant="cta" size="xl" className="w-full" onClick={() => goTo(resumeStep(state))}>
              Revisar mis datos
            </Button>
          ) : (
            <Button variant="cta" size="xl" className="w-full" onClick={retry}>
              <RotateCwIcon data-icon="inline-start" />
              Probar de nuevo
            </Button>
          )
        }
      >
        <Alert variant="destructive">
          <AlertDescription>{messageOf(submission.error)}</AlertDescription>
        </Alert>
      </ScreenLayout>
    );
  }

  const logo = currentLogo(state);
  const products = state.products.filter((product) => !product.archived);
  const imported = instagramPhotos(state).length;
  const photos = readyPhotos(state).length;

  return (
    <ScreenLayout
      title={state.business.name ? `¡Listo, ${state.business.name}!` : "¡Listo!"}
      subtitle="Ya tengo todo. Ahora estudio tu marca y en un minuto te escribo por WhatsApp con lo que entendí."
      footer={<WhatsAppButton href={state.whatsapp_url} label="Volver a WhatsApp" />}
    >
      <section
        aria-label="Lo que me contaste"
        className="flex flex-col gap-4 rounded-[22px] bg-card p-4.5 shadow-bubble motion-safe:animate-rise motion-safe:[animation-delay:.2s]"
      >
        <div className="flex items-center gap-3">
          {logo && (
            <div className="flex size-12 shrink-0 items-center justify-center overflow-hidden rounded-full bg-muted">
              {/* eslint-disable-next-line @next/next/no-img-element -- signed Storage URL */}
              <img src={logo.url} alt="" className="size-full object-contain" />
            </div>
          )}
          <div className="flex min-w-0 flex-col">
            <p className="truncate font-heading text-xl font-extrabold tracking-tight">{state.business.name}</p>
            {state.business.category && (
              <p className="truncate text-sm text-muted-foreground">
                {[state.business.category, state.business.location].filter(Boolean).join(" · ")}
              </p>
            )}
          </div>
        </div>
        <dl className="grid grid-cols-[96px_1fr] gap-x-3 gap-y-3.5 rounded-[18px] bg-muted p-4 text-[15px]">
          <SummaryRow label="Productos">{products.map((product) => product.name).join(" · ")}</SummaryRow>
          {state.brand.colors.length > 0 && (
            <SummaryRow label="Colores">
              <span className="flex gap-1.5" aria-label={state.brand.colors.join(", ")}>
                {state.brand.colors.map((color) => (
                  <span
                    key={color}
                    className="size-6 rounded-full shadow-[inset_0_0_0_1px_rgb(14_42_32/0.12)]"
                    style={{ background: color }}
                  />
                ))}
              </span>
            </SummaryRow>
          )}
          <SummaryRow label="Fotos">
            {photos}
            {imported > 0 && <span className="text-muted-foreground"> ({imported} de Instagram)</span>}
          </SummaryRow>
          <SummaryRow label="Instagram">
            {isInstagramConnected(state) && state.instagram.handle ? (
              <span className="flex items-center gap-1 font-semibold text-primary">
                <CheckIcon className="size-4" strokeWidth={2.6} aria-hidden />
                {atHandle(state.instagram.handle)}
              </span>
            ) : (
              <span className="text-muted-foreground">Lo conectás cuando quieras</span>
            )}
          </SummaryRow>
        </dl>
      </section>

      <Bubble from="neitor" className="px-4.5 py-3 sm:max-w-fit" rowClassName="my-0 motion-safe:animate-rise motion-safe:[animation-delay:.5s]">
        <span className="flex gap-1.5 py-1" role="img" aria-label="Neitor está escribiendo">
          {[0, 1, 2].map((dot) => (
            <span
              key={dot}
              className="size-2 rounded-full bg-ld-sage motion-safe:animate-hop"
              style={{ animationDelay: `${dot * 0.15}s` }}
            />
          ))}
        </span>
      </Bubble>
    </ScreenLayout>
  );
}

function SummaryRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="pt-0.5">
        <Label>{label}</Label>
      </dt>
      <dd className="min-w-0">{children}</dd>
    </>
  );
}
