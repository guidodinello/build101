"use client";

import type { ReactNode } from "react";
import { ArrowRightIcon, ChevronLeftIcon, MessageCircleIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { ScreenLayout } from "@/components/onboarding/screen-layout";
import { useWizard } from "@/components/onboarding/wizard-context";
import { STEPS } from "@/lib/onboarding";

type WizardStepProps = {
  step: (typeof STEPS)[number];
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
  const index = STEPS.indexOf(step);
  const previous = STEPS[index - 1];

  return (
    <ScreenLayout
      header={
        <header className="sticky top-0 z-10 flex flex-col gap-2.5 bg-background px-4 pt-2 pb-1">
          <div className="flex items-center justify-between">
            <Button
              type="button"
              variant="ghost"
              size="icon-lg"
              className="-ml-2.5"
              aria-label="Paso anterior"
              disabled={!previous}
              onClick={() => previous && goTo(previous)}
            >
              <ChevronLeftIcon />
            </Button>
            <p className="text-[13px] font-semibold text-muted-foreground">
              Paso {index + 1} de {STEPS.length}
            </p>
            <a
              href={state.whatsapp_url}
              className="-mr-1 flex h-11 items-center gap-1.5 px-1 text-[13px] font-semibold text-primary"
            >
              <MessageCircleIcon className="size-4" aria-hidden />
              WhatsApp
            </a>
          </div>
          <Progress
            value={((index + 1) / STEPS.length) * 100}
            aria-label={`Paso ${index + 1} de ${STEPS.length}`}
          />
        </header>
      }
      icon={icon}
      title={title}
      subtitle={subtitle}
      onSubmit={onSubmit}
      footer={
        footer ?? (
          <Button type="submit" size="xl" className="w-full" disabled={pending}>
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
