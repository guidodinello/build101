"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowRightIcon, CheckIcon, LockIcon, MessageCircleCheckIcon, SparklesIcon } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { WizardStep } from "@/components/onboarding/wizard-step";
import { useWizard } from "@/components/onboarding/wizard-context";
import { messageOf, onboardingApi } from "@/lib/api";
import { atHandle, isInstagramConnected } from "@/lib/onboarding";

const CONNECT_FAILED = "No pude conectar tu Instagram. Probá de nuevo.";

export function InstagramStep() {
  const { token, state, setState, goTo } = useWizard();
  const searchParams = useSearchParams();
  const returned = searchParams.get("connected");
  const [connecting, setConnecting] = useState(returned === "1");
  const [error, setError] = useState<string | null>(returned === "0" ? CONNECT_FAILED : null);
  const refreshed = useRef(false);

  useEffect(() => {
    if (returned === null || refreshed.current) return;
    refreshed.current = true;

    onboardingApi
      .getState(token)
      .then(setState, (refreshError: unknown) => setError(messageOf(refreshError)))
      .finally(() => {
        setConnecting(false);
        window.history.replaceState(null, "", "?step=instagram");
      });
  }, [returned, token, setState]);

  async function connect() {
    setConnecting(true);
    setError(null);
    try {
      const { auth_url } = await onboardingApi.connectInstagram(token);
      window.location.assign(auth_url);
    } catch (connectError) {
      setError(messageOf(connectError));
      setConnecting(false);
    }
  }

  const connected = isInstagramConnected(state);
  const failed = state.instagram.status === "error" || !!error;

  return (
    <WizardStep
      step="instagram"
      title="¿Tenés Instagram? Conectalo"
      subtitle="Leo tus posts y tus fotos para aprender cómo hablás. Así te pregunto menos."
      footer={
        connected ? (
          <Button variant="cta" size="xl" className="w-full" onClick={() => goTo("products")}>
            Siguiente
            <ArrowRightIcon data-icon="inline-end" />
          </Button>
        ) : (
          <div className="flex flex-col gap-1.5">
            <Button variant="cta" size="xl" className="w-full" disabled={connecting} onClick={connect}>
              {connecting ? (
                <Spinner data-icon="inline-start" aria-label="Conectando" />
              ) : (
                <InstagramGlyph className="size-5" />
              )}
              Conectar Instagram
            </Button>
            <Button
              variant="link"
              size="lg"
              className="w-full text-foreground underline underline-offset-3"
              disabled={connecting}
              onClick={() => goTo("products")}
            >
              No tengo, o lo hago después
            </Button>
          </div>
        )
      }
    >
      {connected ? (
        <div className="flex items-center gap-3.5 rounded-[22px] bg-card p-4 shadow-bubble">
          <span className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <CheckIcon className="size-6" strokeWidth={2.6} aria-hidden />
          </span>
          <div className="flex min-w-0 flex-col gap-0.5">
            <p className="truncate text-[17px] font-bold">
              {state.instagram.handle ? `${atHandle(state.instagram.handle)} conectado` : "Instagram conectado"}
            </p>
            <p className="text-[15px] leading-snug text-muted-foreground">
              Ya estoy trayendo tus fotos. Las vas a ver en el paso de fotos.
            </p>
          </div>
        </div>
      ) : (
        <ul className="flex flex-col gap-4">
          <Reassurance icon={<MessageCircleCheckIcon className="size-5" aria-hidden />}>
            Nunca publico nada sin que lo apruebes por WhatsApp.
          </Reassurance>
          <Reassurance icon={<LockIcon className="size-5" aria-hidden />}>
            Entrás desde la página de Instagram. Nunca veo tu contraseña.
          </Reassurance>
          <Reassurance icon={<SparklesIcon className="size-5" aria-hidden />}>
            Traigo tus fotos y tus textos para aprender tu estilo y lo que le gusta a tu gente.
          </Reassurance>
        </ul>
      )}

      {!connected && failed && !connecting && (
        <Alert variant="destructive">
          <AlertDescription>{error ?? CONNECT_FAILED}</AlertDescription>
        </Alert>
      )}
    </WizardStep>
  );
}

function Reassurance({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <li className="flex items-center gap-3.5 text-base leading-snug">
      <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary">
        {icon}
      </span>
      <span>{children}</span>
    </li>
  );
}

function InstagramGlyph({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      aria-hidden
    >
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.3" cy="6.7" r="0.6" fill="currentColor" />
    </svg>
  );
}
