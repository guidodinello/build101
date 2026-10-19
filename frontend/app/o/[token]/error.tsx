"use client";

import { RotateCwIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScreenLayout } from "@/components/onboarding/screen-layout";

export default function OnboardingError({ retry }: { error: unknown; retry: () => void }) {
  return (
    <ScreenLayout
      title="No pude cargar tus datos"
      subtitle="Puede ser la conexión. Probá de nuevo en un ratito."
      footer={
        <Button variant="cta" size="xl" className="w-full" onClick={() => retry()}>
          <RotateCwIcon data-icon="inline-start" />
          Probar de nuevo
        </Button>
      }
    />
  );
}
