import { MessageCircleIcon } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const FALLBACK_WHATSAPP_URL = process.env.NEXT_PUBLIC_WHATSAPP_URL ?? "https://wa.me/";

export function WhatsAppButton({ href, label }: { href: string; label: string }) {
  return (
    <a href={href} className={cn(buttonVariants({ size: "xl" }), "w-full")}>
      <MessageCircleIcon data-icon="inline-start" />
      {label}
    </a>
  );
}
