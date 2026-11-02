import { SendIcon } from "lucide-react";
import { Bubble, Display } from "@/components/landing/chat";
import { WHATSAPP_START_URL } from "@/lib/whatsapp";

export function FinalCta() {
  return (
    <section
      aria-labelledby="final-title"
      className="mt-32 rounded-[40px] bg-ld-forest p-[clamp(24px,6vw,72px)] shadow-[0_40px_80px_-40px_rgb(14_42_32/0.8)] motion-safe:reveal-on-scroll"
    >
      <Bubble from="neitor" time="ahora" className="px-6 pt-6 pb-4 sm:max-w-full sm:px-8.5 sm:pt-7.5" rowClassName="my-0">
        <Display as="h2" id="final-title" className="text-[clamp(2.6rem,6vw,5.6rem)] leading-[0.95]">
          Cuando quieras. Escribime.
        </Display>
      </Bubble>
      <Bubble from="neitor" className="px-4.5 py-3 sm:max-w-fit" rowClassName="mt-2.5">
        <span className="flex gap-1.5 py-1" role="img" aria-label="Neitor está escribiendo">
          {[0, 1, 2].map((dot) => (
            <span
              key={dot}
              className="size-2 rounded-full bg-[#9db0a6] motion-safe:animate-hop"
              style={{ animationDelay: `${dot * 0.15}s` }}
            />
          ))}
        </span>
      </Bubble>
      <a
        href={WHATSAPP_START_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="group mt-7 flex items-center gap-3 rounded-full outline-none focus-visible:ring-3 focus-visible:ring-ld-accent/70 focus-visible:ring-offset-4 focus-visible:ring-offset-ld-forest"
      >
        <span className="flex min-h-16.5 min-w-0 flex-1 items-center rounded-full bg-white/9 px-5 text-base font-medium text-ld-on-dark-muted shadow-[inset_0_0_0_1px_rgb(255_255_255/0.14)] transition-colors group-hover:bg-white/12 sm:px-7 sm:text-[19px]">
          <span className="truncate">Escribile a Neitor por WhatsApp…</span>
        </span>
        <span
          aria-hidden="true"
          className="flex size-16.5 shrink-0 items-center justify-center rounded-full bg-ld-accent text-ld-ink shadow-[0_12px_28px_-10px_rgb(255_106_26/0.8)] transition-transform duration-200 ease-out group-hover:-translate-y-0.5"
        >
          <SendIcon className="size-6.5" />
        </span>
      </a>
    </section>
  );
}
