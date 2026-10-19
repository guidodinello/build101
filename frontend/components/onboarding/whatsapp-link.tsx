import { MessageCircleIcon } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { WHATSAPP_URL } from "@/lib/whatsapp";

export const FALLBACK_WHATSAPP_URL = WHATSAPP_URL;

export function WhatsAppButton({ href, label }: { href: string; label: string }) {
  return (
    <a href={href} className={cn(buttonVariants({ variant: "cta", size: "xl" }), "w-full")}>
      <MessageCircleIcon data-icon="inline-start" />
      {label}
    </a>
  );
}
