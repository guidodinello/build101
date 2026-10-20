import Image from "next/image";
import { CheckIcon, ClipboardListIcon, PlayIcon } from "lucide-react";
import { Bubble, DayChip, Label, Timestamp } from "@/components/landing/chat";
import { cn } from "@/lib/utils";
import oakTable from "@/components/landing/photos/oak-table.jpg";
import workshopHands from "@/components/landing/photos/workshop-hands.jpg";
import workshop from "@/components/landing/photos/workshop.jpg";

const BRAND_COLORS = [
  { name: "Nogal", hex: "#6b3e26" },
  { name: "Arena", hex: "#e9dcc6" },
  { name: "Musgo", hex: "#4b5d3a" },
];

const WAVEFORM = [6, 14, 22, 10, 18, 8, 24, 12, 4, 16, 10, 20, 8, 14, 6, 18, 10, 4, 12, 6, 8, 4];

const OPTIONS = [
  { photo: workshop, alt: "Opción 1, el taller", frame: "bg-[#e9dcc6]", position: "object-center" },
  { photo: workshopHands, alt: "Opción 2, manos trabajando una tabla", frame: "bg-[#6b3e26]", position: "object-center", picked: true },
  { photo: oakTable, alt: "Opción 3, la mesa de roble", frame: "bg-[#4b5d3a]", position: "object-[50%_85%]" },
];

export function HowItWorks() {
  return (
    <section aria-labelledby="how-title">
      <DayChip id="how" headingId="how-title">
        Cómo funciona · Lunes
      </DayChip>

      <Bubble from="owner" time="09:02" rowClassName="motion-safe:reveal-on-scroll">
        Hola
      </Bubble>
      <Bubble from="neitor" time="09:02" className="sm:max-w-115" rowClassName="motion-safe:reveal-on-scroll">
        ¡Hola! Primero contame de tu negocio. Son unos 5 minutos:
        <div className="mt-3 flex items-center gap-3.5 rounded-[18px] bg-ld-mist p-3">
          <span aria-hidden="true" className="flex size-14 shrink-0 items-center justify-center rounded-[14px] bg-ld-forest text-ld-on-dark">
            <ClipboardListIcon className="size-6" />
          </span>
          <span className="flex flex-col gap-0.5">
            <span className="text-base font-bold">Contanos de tu negocio</span>
            <span className="text-sm text-ld-muted">Productos, logo, algunas fotos, cómo hablás.</span>
            <span className="text-[13px] text-ld-subtle">neitor.ai</span>
          </span>
        </div>
      </Bubble>

      <Bubble from="neitor" className="px-0 pt-4 pb-0 sm:max-w-135" rowClassName="motion-safe:reveal-on-scroll">
        <p className="px-5">Esto es lo que entendí de tu marca. ¿Es así?</p>
        <dl className="mx-3.5 mt-3.5 grid grid-cols-[104px_1fr] gap-3.5 rounded-[18px] bg-ld-mist p-4.5 text-[15px] sm:grid-cols-[116px_1fr]">
          <dt><Label>Voz</Label></dt>
          <dd>Cálida, orgullosa del oficio, nunca insistente</dd>
          <dt className="pt-1.5"><Label>Colores</Label></dt>
          <dd className="flex gap-2">
            {BRAND_COLORS.map((color) => (
              <span
                key={color.name}
                title={color.name}
                className="size-7.5 rounded-full shadow-[inset_0_0_0_1px_rgb(0_0_0/0.08)]"
                style={{ backgroundColor: color.hex }}
              >
                <span className="sr-only">{color.name}</span>
              </span>
            ))}
          </dd>
          <dt><Label>Más vendidos</Label></dt>
          <dd>Mesa redonda de roble · Estante de lapacho · Banco</dd>
          <dt><Label>Habla de</Label></dt>
          <dd>Piezas nuevas · el taller · el cuidado de la madera</dd>
        </dl>
        <Timestamp time="09:09" className="px-4" />
        <div className="mt-2 flex text-base font-bold" aria-hidden="true">
          <span className="flex min-h-13 flex-1 items-center justify-center border-t border-ld-line text-ld-forest">Sí, es mi marca</span>
          <span className="flex min-h-13 flex-1 items-center justify-center border-t border-l border-ld-line text-ld-forest">Corregir algo</span>
        </div>
      </Bubble>

      <DayChip className="mt-14 sm:mt-14">Viernes</DayChip>
      <Bubble from="owner" time="18:31" className="min-w-75" rowClassName="motion-safe:reveal-on-scroll">
        <div className="flex items-center gap-3">
          <span aria-hidden="true" className="flex size-10 items-center justify-center rounded-full bg-ld-on-dark text-ld-forest">
            <PlayIcon className="size-4 fill-current" />
          </span>
          <span aria-hidden="true" className="flex h-7 items-center gap-1">
            {WAVEFORM.map((height, index) => (
              <span key={index} className="w-[3px] rounded-full bg-ld-sage" style={{ height }} />
            ))}
          </span>
          <span className="text-[13px] font-medium text-ld-sage">
            <span className="sr-only">Audio, </span>0:07
          </span>
        </div>
        <p className="mt-2.5 text-[15px] text-[#cfe0d7] italic">&ldquo;Haceme un post para la promo del finde, 10% en estantes.&rdquo;</p>
      </Bubble>

      <Bubble from="neitor" time="18:33" className="sm:max-w-145" rowClassName="motion-safe:reveal-on-scroll">
        Escuché tu audio. Te armé tres opciones con tus fotos. ¿Cuál te gusta más?
        <ul className="mt-3 grid grid-cols-3 gap-2">
          {OPTIONS.map((option, index) => (
            <li key={option.alt} className="flex flex-col items-center gap-2">
              <span
                className={cn(
                  "w-full rounded-[14px] p-2",
                  option.frame,
                  option.picked && "ring-[2.5px] ring-ld-accent ring-offset-[3px]",
                )}
              >
                <Image
                  src={option.photo}
                  alt={option.alt}
                  sizes="(min-width: 640px) 170px, 28vw"
                  placeholder="blur"
                  className={cn("h-28 w-full rounded-lg object-cover sm:h-34", option.position)}
                />
              </span>
              <span className={cn("text-[13px] font-semibold", option.picked ? "text-ld-accent-ink" : "text-ld-muted")}>
                {option.picked ? `${index + 1} · elegida` : index + 1}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-[15px] text-ld-muted">Nada es público hasta que lo aprobás.</p>
      </Bubble>
      <Bubble from="owner" time="18:35" rowClassName="motion-safe:reveal-on-scroll">
        La segunda. <strong>Aprobar</strong>
      </Bubble>
      <Bubble from="neitor" time="18:35" rowClassName="motion-safe:reveal-on-scroll">
        <span className="inline-flex items-center gap-2">
          <CheckIcon className="size-4.5 text-green-600" strokeWidth={2.6} aria-hidden="true" />
          <span>
            Programado para el <strong>sábado a las 10:00</strong> en Instagram.
          </span>
        </span>
      </Bubble>
    </section>
  );
}
