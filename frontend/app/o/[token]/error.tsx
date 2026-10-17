"use client";

import { RotateCwIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScreenLayout } from "@/components/onboarding/screen-layout";

export default function OnboardingError({ retry }: { error: unknown; retry: () => void }) {
  return (
    <ScreenLayout
      title="No pudimos cargar tus datos"
      footer={
        <Button size="xl" className="w-full" onClick={() => retry()}>
          <RotateCwIcon data-icon="inline-start" />
          Probar de nuevo
        </Button>
      }
    >
      <p className="text-[17px] leading-relaxed text-muted-foreground">
        Puede ser la conexión. Probá de nuevo en un ratito.
      </p>
    </ScreenLayout>
  );
}
