import type { ReactNode } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { MessageCircleIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { WHATSAPP_START_URL } from "@/lib/whatsapp";

const ctaVariants = cva(
  "inline-flex min-h-13.5 items-center justify-center gap-2.5 rounded-full px-6 text-[17px] font-bold transition-[background-color,transform] duration-200 ease-out outline-none focus-visible:ring-3 focus-visible:ring-ld-forest/60 focus-visible:ring-offset-2",
  {
    variants: {
      variant: {
        primary: "bg-ld-accent text-ld-ink shadow-cta hover:-translate-y-px hover:bg-ld-accent-hover",
        soft: "bg-[#edf2ee] font-semibold text-ld-forest hover:bg-[#e2eae4]",
      },
      size: {
        default: "",
        sm: "min-h-11.5 px-4.5 text-[15px]",
      },
    },
    defaultVariants: { variant: "primary", size: "default" },
  },
);

type CtaLinkProps = VariantProps<typeof ctaVariants> & {
  href?: string;
  icon?: boolean;
  className?: string;
  children: ReactNode;
};

export function CtaLink({ href = WHATSAPP_START_URL, icon, variant, size, className, children }: CtaLinkProps) {
  return (
    <a href={href} className={cn(ctaVariants({ variant, size }), className)}>
      {icon && <MessageCircleIcon className="size-5" aria-hidden="true" />}
      {children}
    </a>
  );
}
