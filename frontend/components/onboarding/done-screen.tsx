"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { CheckIcon, RotateCwIcon } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { ScreenLayout } from "@/components/onboarding/screen-layout";
import { WhatsAppButton } from "@/components/onboarding/whatsapp-link";
import { useWizard } from "@/components/onboarding/wizard-context";
import { ApiError, messageOf, onboardingApi } from "@/lib/api";
import { atHandle, currentLogo, readyPhotos, resumeStep } from "@/lib/onboarding";

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
      <ScreenLayout title="Un segundo…">
        <p className="flex items-center gap-2 text-[17px] text-muted-foreground">
          <Spinner className="size-5" aria-label="Guardando" />
          Estamos guardando todo.
        </p>
      </ScreenLayout>
    );
  }

  if (submission.status === "failed") {
    const missingData = submission.error instanceof ApiError && submission.error.status === 422;
    return (
      <ScreenLayout
        title="Nos falta algo"
        footer={
          missingData ? (
            <Button size="xl" className="w-full" onClick={() => goTo(resumeStep(state))}>
              Revisar mis datos
            </Button>
          ) : (
            <Button size="xl" className="w-full" onClick={retry}>
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
  const products = state.products.filter((product) => !product.archived).length;

  return (
    <ScreenLayout
      icon={
        <div className="mt-6 flex size-16 items-center justify-center rounded-full bg-accent text-accent-foreground">
          <CheckIcon className="size-8" strokeWidth={2.4} aria-hidden />
        </div>
      }
      title={<span className="text-[34px]">¡Listo!</span>}
      footer={<WhatsAppButton href={state.whatsapp_url} label="Volver a WhatsApp" />}
    >
      <p className="-mt-2 text-[17px] leading-relaxed text-pretty">
        Ya tenemos todo. En un minuto te escribimos por WhatsApp con lo que entendimos de tu marca.
      </p>

      <section aria-label="Resumen" className="flex flex-col rounded-2xl border bg-card px-4 pt-4 pb-1">
        <div className="flex items-center gap-3 pb-3.5">
          {logo && (
            <div className="flex size-13 shrink-0 items-center justify-center overflow-hidden rounded-md bg-muted">
              {/* eslint-disable-next-line @next/next/no-img-element -- signed Storage URL */}
              <img src={logo.url} alt="" className="size-full object-contain" />
            </div>
          )}
          <div className="flex min-w-0 flex-col gap-1.5">
            <p className="truncate text-[17px] font-bold">{state.business.name}</p>
            {state.brand.colors.length > 0 && (
              <div className="flex gap-1.5" aria-label="Tus colores">
                {state.brand.colors.map((color) => (
                  <span
                    key={color}
                    className="size-5.5 rounded-[6px] shadow-[inset_0_0_0_1px_rgb(31_27_22/0.12)]"
                    style={{ background: color }}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
        <dl>
          <SummaryRow label="Productos">{products}</SummaryRow>
          <SummaryRow label="Fotos">{readyPhotos(state).length}</SummaryRow>
          <SummaryRow label="Posts por semana">{state.preferences?.posts_per_week ?? "—"}</SummaryRow>
          <SummaryRow label="Instagram">
            {state.instagram.status === "connected" && state.instagram.handle ? (
              <span className="flex items-center gap-1 font-semibold text-primary">
                <CheckIcon className="size-4" strokeWidth={2.6} aria-hidden />
                {atHandle(state.instagram.handle)}
              </span>
            ) : (
              <span className="text-muted-foreground">Lo conectás después</span>
            )}
          </SummaryRow>
        </dl>
      </section>
    </ScreenLayout>
  );
}

function SummaryRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-t border-muted py-3 text-[14.5px]">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
