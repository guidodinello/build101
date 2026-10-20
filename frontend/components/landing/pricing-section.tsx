import type { ReactNode } from "react";
import { Bubble, DayChip, Label } from "@/components/landing/chat";
import { CtaLink } from "@/components/landing/cta-link";
import { cn } from "@/lib/utils";

function Plan({ name, badge, price, dark, children, action }: {
  name: string;
  badge?: string;
  price: ReactNode;
  dark?: boolean;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <li
      className={cn(
        "flex flex-col gap-4 rounded-[30px] p-7",
        dark && "bg-ld-forest text-ld-on-dark shadow-panel",
        !dark && "bg-white shadow-[0_0_0_1px_rgb(14_42_32/0.06),0_18px_40px_-26px_rgb(14_42_32/0.35)]",
      )}
    >
      <div className="flex items-center justify-between">
        <h3 className="font-heading text-[22px] font-extrabold tracking-tight">{name}</h3>
        {badge ? (
          <span className="rounded-full bg-ld-accent px-2.5 py-1.5 text-xs font-bold tracking-[0.06em] text-ld-ink uppercase">
            {badge}
          </span>
        ) : null}
      </div>
      <p>{price}</p>
      <ul className={cn("flex grow list-disc flex-col gap-2 pl-5 text-base", dark && "text-[#d6e4dc]")}>
        {children}
      </ul>
      {action}
    </li>
  );
}

function Amount({ value, muted }: { value: string; muted: string }) {
  return (
    <span className="whitespace-nowrap">
      <span className="font-heading text-[clamp(3rem,5vw,3.75rem)] leading-none font-extrabold tracking-[-0.045em]">
        {value}
      </span>
      <span className={muted}> / mes</span>
    </span>
  );
}

export function PricingSection() {
  return (
    <section aria-labelledby="pricing-title">
      <DayChip id="pricing" headingId="pricing-title">
        Precios de lanzamiento
      </DayChip>
      <Bubble from="neitor" time="18:40" rowClassName="motion-safe:reveal-on-scroll">
        Probame gratis. Cuando quieras más, elegí un plan, con pago mensual.
      </Bubble>
      <ul className="mt-3 grid gap-3.5 motion-safe:reveal-on-scroll md:grid-cols-3">
        <Plan
          name="Gratis"
          price={<Amount value="US$0" muted="text-ld-muted" />}
          action={<CtaLink variant="soft">Probalo gratis</CtaLink>}
        >
          <li>Hasta 3 posts o carruseles por mes</li>
          <li>Hechos con tus fotos</li>
          <li>Publicados en tu Instagram</li>
          <li>Sin tarjeta</li>
        </Plan>
        <Plan
          name="Básico"
          badge="Recomendado"
          dark
          price={<Amount value="US$29" muted="text-ld-sage" />}
          action={<CtaLink>Empezá</CtaLink>}
        >
          <li>Posts y carruseles con tus fotos</li>
          <li>Un plan de contenido semanal, cuando lo pidas</li>
          <li>Publicá ya o programá en Instagram</li>
          <li>Cada post lo aprobás vos, en WhatsApp</li>
        </Plan>
        <Plan
          name="Pro"
          price={<Amount value="US$49" muted="text-ld-muted" />}
          action={<CtaLink variant="soft">Anotame en la lista Pro</CtaLink>}
        >
          <li>Todo lo de Básico</li>
          <li>Respuestas a comentarios y mensajes <Label>pronto</Label></li>
          <li>Avisos de ventas en WhatsApp <Label>pronto</Label></li>
          <li>Un resumen semanal de resultados <Label>pronto</Label></li>
        </Plan>
      </ul>
    </section>
  );
}
