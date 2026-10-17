"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowRightIcon, CircleCheckIcon, LockIcon, MessageCircleCheckIcon } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { WizardStep } from "@/components/onboarding/wizard-step";
import { useWizard } from "@/components/onboarding/wizard-context";
import { messageOf, onboardingApi } from "@/lib/api";
import { atHandle } from "@/lib/onboarding";

const RETURN_PARAMS = ["step", "connected"];

export function InstagramStep() {
  const { token, state, setState, goTo } = useWizard();
  const searchParams = useSearchParams();
  const returning = searchParams.get("connected") === "1";
  const [connecting, setConnecting] = useState(returning);
  const [error, setError] = useState<string | null>(null);
  const callbackSent = useRef(false);

  useEffect(() => {
    if (!returning || callbackSent.current) return;
    callbackSent.current = true;

    const query = Object.fromEntries(
      [...searchParams.entries()].filter(([key]) => !RETURN_PARAMS.includes(key)),
    );
    const accountId = query.accountId ?? query.account_id;
    onboardingApi
      .instagramCallback(token, query, accountId)
      .then(setState, (callbackError: unknown) => setError(messageOf(callbackError)))
      .finally(() => {
        setConnecting(false);
        window.history.replaceState(null, "", "?step=instagram");
      });
  }, [returning, searchParams, token, setState]);

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

  const connected = state.instagram.status === "connected";
  const failed = state.instagram.status === "error" || !!error;

  return (
    <WizardStep
      step="instagram"
      icon={
        <div className="flex size-18 items-center justify-center rounded-[22px] bg-foreground text-background">
          <svg
            viewBox="0 0 24 24"
            className="size-9"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.8}
            strokeLinecap="round"
            aria-hidden
          >
            <rect x="3" y="3" width="18" height="18" rx="5" />
            <circle cx="12" cy="12" r="4" />
            <circle cx="17.3" cy="6.7" r="0.6" fill="currentColor" />
          </svg>
        </div>
      }
      title="Conectá tu Instagram"
      subtitle="Publicamos solo lo que vos apruebes."
      footer={
        connected ? (
          <Button size="xl" className="w-full" onClick={() => goTo("done")}>
            Siguiente
            <ArrowRightIcon data-icon="inline-end" />
          </Button>
        ) : (
          <div className="flex flex-col gap-2">
            <Button size="xl" className="w-full" disabled={connecting} onClick={connect}>
              {connecting && <Spinner data-icon="inline-start" aria-label="Conectando" />}
              Conectar Instagram
            </Button>
            <Button
              variant="link"
              size="lg"
              className="w-full text-foreground underline underline-offset-3"
              disabled={connecting}
              onClick={() => goTo("done")}
            >
              Lo hago después
            </Button>
          </div>
        )
      }
    >
      <ul className="flex flex-col gap-3.5">
        <Reassurance icon={<MessageCircleCheckIcon className="size-4.5" aria-hidden />}>
          Cada post te llega primero por WhatsApp para que lo apruebes.
        </Reassurance>
        <Reassurance icon={<LockIcon className="size-4.5" aria-hidden />}>
          Iniciás sesión en la página de Instagram, nunca nos das tu contraseña.
        </Reassurance>
      </ul>

      {connected && (
        <p className="flex items-center gap-2 rounded-lg bg-primary-soft px-3.5 py-3 text-[15px] font-semibold text-primary">
          <CircleCheckIcon className="size-5" aria-hidden />
          {state.instagram.handle ? `${atHandle(state.instagram.handle)} conectado` : "Instagram conectado"}
        </p>
      )}

      {!connected && failed && !connecting && (
        <Alert variant="destructive">
          <AlertDescription>
            {error ?? "No pudimos conectar tu Instagram. Probá de nuevo."}
          </AlertDescription>
        </Alert>
      )}
    </WizardStep>
  );
}

function Reassurance({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <li className="flex items-start gap-3 text-[15px] leading-snug">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-[10px] bg-primary-soft text-primary">
        {icon}
      </span>
      <span className="pt-1">{children}</span>
    </li>
  );
}
