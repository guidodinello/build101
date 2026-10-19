import { ScreenLayout } from "@/components/onboarding/screen-layout";
import { FALLBACK_WHATSAPP_URL, WhatsAppButton } from "@/components/onboarding/whatsapp-link";

export function ExpiredLink() {
  return (
    <ScreenLayout
      title="Este link venció"
      subtitle={
        <>
          Escribime <strong className="text-foreground">“link”</strong> por WhatsApp y te mando uno nuevo.
        </>
      }
      footer={<WhatsAppButton href={FALLBACK_WHATSAPP_URL} label="Ir a WhatsApp" />}
    />
  );
}
