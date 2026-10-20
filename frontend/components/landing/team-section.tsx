import type { LucideIcon } from "lucide-react";
import { CalendarDaysIcon, ImageIcon, PenLineIcon, SendIcon } from "lucide-react";
import { Bubble, DayChip, Display, Label } from "@/components/landing/chat";
import { NeitorAvatar } from "@/components/landing/site-header";
import { cn } from "@/lib/utils";

const SPECIALISTS: { role: string; job: string; icon: LucideIcon }[] = [
  { role: "Estrategia", job: "Planifica tu semana según lo que vendés y las fechas que importan.", icon: CalendarDaysIcon },
  { role: "Redacción", job: "Escribe los textos con tu voz y tus palabras.", icon: PenLineIcon },
  { role: "Dirección de arte", job: "Convierte tus fotos reales en posts con tu marca. Nunca altera tu producto.", icon: ImageIcon },
  { role: "Publicación", job: "Publica o programa en Instagram, solo después de que aprobás.", icon: SendIcon },
];

const TRACE = [
  { who: "Estrategia", what: "los estantes se venden mucho y es viernes: arrancamos con el finde." },
  { who: "Redacción", what: "corto, cálido, el 10% bien adelante, sin presionar." },
  { who: "Dirección de arte", what: "tres versiones de tu foto en nogal, arena y musgo." },
  { who: "Vos", what: "elegiste la opción 2 y tocaste Aprobar.", owner: true },
  { who: "Publicación", what: "programado para el sábado a las 10:00." },
];

export function TeamSection() {
  return (
    <section aria-labelledby="team-title">
      <DayChip id="team">Quién está detrás de Neitor</DayChip>
      <Bubble
        from="neitor"
        time="18:36"
        className="px-6 pt-6 pb-4 sm:max-w-[92%] sm:px-8.5 sm:pt-7.5"
        rowClassName="motion-safe:reveal-on-scroll"
      >
        <Display as="h2" id="team-title" className="text-[clamp(2.1rem,4.4vw,3.75rem)] leading-none">
          Vos hablás solo conmigo. Detrás mío, un equipo entero trabaja en cada post.
        </Display>
        <div className="mt-7 flex flex-wrap gap-7">
          <ul className="flex flex-[1_1_320px] flex-col gap-4.5">
            <li className="flex gap-3.5">
              <NeitorAvatar className="size-11.5 text-lg" />
              <div>
                <strong>Coordinación</strong> <Label className="ml-1 text-ld-accent-ink">ese soy yo</Label>
                <p className="text-base text-ld-muted">Habla con vos, entiende lo que necesitás y coordina al equipo.</p>
              </div>
            </li>
            {SPECIALISTS.map(({ role, job, icon: Icon }) => (
              <li key={role} className="flex gap-3.5">
                <span aria-hidden="true" className="flex size-11.5 shrink-0 items-center justify-center rounded-full bg-[#e6eee8] text-ld-forest">
                  <Icon className="size-5" />
                </span>
                <div>
                  <strong>{role}</strong>
                  <p className="text-base text-ld-muted">{job}</p>
                </div>
              </li>
            ))}
          </ul>
          <div className="flex-[1_1_300px] rounded-[22px] bg-ld-mist px-6 py-5.5">
            <Label className="mb-4 block">Cómo se hizo la promo del finde</Label>
            <ol className="flex flex-col gap-4.5 border-l-2 border-dashed border-[#c3d2c8] pl-5 text-[15px]">
              {TRACE.map((step) => (
                <li key={step.who} className="relative">
                  <span
                    aria-hidden="true"
                    className={cn(
                      "absolute top-1 -left-[29px] size-3.5 rounded-full ring-3 ring-ld-mist",
                      step.owner ? "bg-ld-accent" : "bg-ld-forest",
                    )}
                  />
                  <strong>{step.who}</strong> · {step.what}
                </li>
              ))}
            </ol>
          </div>
        </div>
      </Bubble>
    </section>
  );
}
