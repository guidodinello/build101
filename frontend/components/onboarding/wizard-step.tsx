"use client";

import type { ReactNode } from "react";
import { ArrowRightIcon, ChevronLeftIcon, MessageCircleIcon } from "lucide-react";
import { NeitorAvatar } from "@/components/landing/site-header";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { ScreenLayout } from "@/components/onboarding/screen-layout";
import { useWizard } from "@/components/onboarding/wizard-context";
import { wizardSteps, type WizardStepId } from "@/lib/onboarding";
import { cn } from "@/lib/utils";

type WizardStepProps = {
  step: WizardStepId;
  title: ReactNode;
  subtitle?: ReactNode;
  icon?: ReactNode;
  children: ReactNode;
  onSubmit?: () => void;
  pending?: boolean;
  footer?: ReactNode;
};

export function WizardStep({
  step,
  title,
  subtitle,
  icon,
  children,
  onSubmit,
  pending = false,
  footer,
}: WizardStepProps) {
  const { state, goTo } = useWizard();
  const steps = wizardSteps(state);
  const index = steps.indexOf(step);
  const previous = steps[index - 1];

  return (
    <ScreenLayout
      header={
        <header className="sticky top-0 z-10 bg-linear-to-b from-background from-60% to-background/0 px-3 pt-3 pb-3">
          <div className="flex items-center gap-2.5 rounded-full bg-white/85 p-1.5 shadow-float backdrop-blur-md backdrop-saturate-150">
            {previous && (
              <button
                type="button"
                aria-label="Paso anterior"
                className="flex size-10 shrink-0 items-center justify-center rounded-full text-primary transition-colors outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-primary/40"
                onClick={() => goTo(previous)}
              >
                <ChevronLeftIcon className="size-5.5" aria-hidden />
              </button>
            )}
            <span className="relative shrink-0">
              <NeitorAvatar className="size-10 text-[19px]" />
              <span
                aria-hidden
                className="absolute -right-px -bottom-px size-2.5 rounded-full bg-green-500 ring-2 ring-white"
              />
            </span>
            <div className="mr-auto flex min-w-0 flex-col">
              <span className="font-heading text-base leading-tight font-extrabold tracking-tight">
                Neitor AI
              </span>
              <span className="truncate text-[13px] leading-tight font-medium text-ld-subtle">
                Paso {index + 1} de {steps.length}
              </span>
            </div>
            <a
              href={state.whatsapp_url}
              className="flex h-10 shrink-0 items-center gap-1.5 rounded-full bg-secondary px-3.5 text-sm font-semibold text-primary transition-colors outline-none hover:bg-[#e2eae4] focus-visible:ring-3 focus-visible:ring-primary/40"
            >
              <MessageCircleIcon className="size-4" aria-hidden />
              WhatsApp
            </a>
          </div>
          <div
            role="progressbar"
            aria-label={`Paso ${index + 1} de ${steps.length}`}
            aria-valuemin={1}
            aria-valuemax={steps.length}
            aria-valuenow={index + 1}
            className="mt-3 flex gap-1.5 px-5"
          >
            {steps.map((id, position) => (
              <span
                key={id}
                className={cn(
                  "h-1 flex-1 rounded-full transition-colors duration-500",
                  position < index && "bg-primary",
                  position === index && "bg-accent",
                  position > index && "bg-track",
                )}
              />
            ))}
          </div>
        </header>
      }
      icon={icon}
      title={title}
      subtitle={subtitle}
      onSubmit={onSubmit}
      footer={
        footer ?? (
          <Button type="submit" variant="cta" size="xl" className="w-full" disabled={pending}>
            {pending ? <Spinner data-icon="inline-start" aria-label="Guardando" /> : null}
            Siguiente
            {pending ? null : <ArrowRightIcon data-icon="inline-end" />}
          </Button>
        )
      }
    >
      {children}
    </ScreenLayout>
  );
}
