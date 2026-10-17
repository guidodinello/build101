import { Link2OffIcon } from "lucide-react";
import { ScreenLayout } from "@/components/onboarding/screen-layout";
import { FALLBACK_WHATSAPP_URL, WhatsAppButton } from "@/components/onboarding/whatsapp-link";

export function ExpiredLink() {
  return (
    <ScreenLayout
      icon={
        <div className="mt-[18dvh] flex size-16 items-center justify-center rounded-[20px] bg-muted text-muted-foreground">
          <Link2OffIcon className="size-7.5" aria-hidden />
        </div>
      }
      title="Este link venció"
      footer={<WhatsAppButton href={FALLBACK_WHATSAPP_URL} label="Ir a WhatsApp" />}
    >
      <p className="-mt-2 text-[17px] leading-relaxed">
        Escribinos <strong>“link”</strong> por WhatsApp y te mandamos uno nuevo.
      </p>
    </ScreenLayout>
  );
}
