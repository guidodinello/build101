import { Bubble, DayChip, Display } from "@/components/landing/chat";
import { cn } from "@/lib/utils";

const PAINS = [
  "Sé que las redes venden. Lo que no tengo es tiempo para planificar, escribir y diseñar posts todas las semanas.",
  "Una agencia o un community manager me sale más de lo que puedo pagar.",
  "Canva, Meta Business Suite, ChatGPT… igual termino en la compu haciendo todo yo.",
  "Así que publico cuando puedo. Mi Instagram parece abandonado.",
];

const VALUES = [
  { title: "Nada que aprender", body: "Todo pasa en un chat de WhatsApp. Texto, fotos, audios." },
  { title: "Conoce tu marca", body: "Tu tono, tus colores, tus productos y tus clientes le dan forma a cada post." },
  { title: "Un equipo, no una herramienta", body: "Estrategia, textos, diseño y publicación, todo coordinado." },
  { title: "Vos tenés el control", body: "Nada se publica sin que vos lo apruebes.", highlight: true },
];

export function ProblemSection() {
  return (
    <section aria-labelledby="why-title">
      <DayChip id="why">¿Te suena?</DayChip>
      {PAINS.map((pain) => (
        <Bubble key={pain} from="owner" className="sm:text-[22px]" rowClassName="motion-safe:reveal-on-scroll">
          {pain}
        </Bubble>
      ))}

      <Bubble
        from="neitor"
        time="08:02"
        className="px-6 pt-6 pb-4 sm:max-w-[92%] sm:px-8.5 sm:pt-7.5"
        rowClassName="mt-6.5 motion-safe:reveal-on-scroll"
      >
        <Display as="h2" id="why-title" className="text-[clamp(2.1rem,4.4vw,3.75rem)] leading-none">
          No necesitás otra app que aprender. Necesitás a alguien que lo haga, como lo harías vos.
        </Display>
        <ul className="mt-7 grid gap-3 text-base leading-snug sm:grid-cols-2">
          {VALUES.map((value) => (
            <li key={value.title} className={cn("rounded-[18px] p-4.5", value.highlight ? "bg-ld-peach" : "bg-ld-mist")}>
              <strong className="mb-1.5 block font-heading text-[19px] font-bold tracking-tight">{value.title}</strong>
              {value.body}
            </li>
          ))}
        </ul>
      </Bubble>
    </section>
  );
}
