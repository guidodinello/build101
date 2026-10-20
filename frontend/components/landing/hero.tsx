import Image from "next/image";
import { CheckIcon } from "lucide-react";
import { ApprovalDemo } from "@/components/landing/approval-demo";
import { Bubble, DayChip, Display } from "@/components/landing/chat";
import { CtaLink } from "@/components/landing/cta-link";
import oakTable from "@/components/landing/photos/oak-table.jpg";

const PROMISES = ["Sin apps para instalar", "Aprobás cada post", "Habla como vos"];

export function Hero() {
  return (
    <section aria-labelledby="hero-title">
      <DayChip className="mt-6 motion-safe:animate-rise sm:mt-6">Hoy</DayChip>

      <Bubble
        from="neitor"
        time="23:41"
        className="px-6 pt-6 pb-4 sm:max-w-[92%] sm:px-8.5 sm:pt-7.5"
        rowClassName="motion-safe:animate-rise motion-safe:[animation-delay:.05s]"
      >
        <Display as="h1" id="hero-title" className="text-[clamp(2.6rem,6vw,5.6rem)] leading-[0.95]">
          Hola, soy Neitor. Tu agencia de marketing, en tu WhatsApp.
        </Display>
      </Bubble>

      <Bubble
        from="neitor"
        time="23:41"
        className="px-6 pt-5 sm:max-w-[68%] sm:text-xl"
        rowClassName="motion-safe:animate-rise motion-safe:[animation-delay:.35s]"
      >
        <p className="mb-4.5 text-pretty">
          Mandame una foto de lo que vendés. Mi equipo planifica el post, lo escribe, lo diseña y lo publica en tu
          Instagram. <strong>Nada sale hasta que tocás Aprobar.</strong>
        </p>
        <div className="flex flex-wrap gap-2.5">
          <CtaLink icon>Empezá en WhatsApp</CtaLink>
          <CtaLink href="#how" variant="soft">
            Mirá cómo funciona
          </CtaLink>
        </div>
      </Bubble>

      <ul className="mt-3.5 flex flex-wrap gap-2 motion-safe:animate-rise motion-safe:[animation-delay:.55s]">
        {PROMISES.map((promise) => (
          <li
            key={promise}
            className="inline-flex min-h-10 items-center gap-2 rounded-full bg-white px-3.5 text-sm font-semibold text-[#2d4a3e] shadow-[0_0_0_1px_rgb(14_42_32/0.08)]"
          >
            <CheckIcon className="size-4 text-ld-forest" strokeWidth={2.4} aria-hidden="true" />
            {promise}
          </li>
        ))}
      </ul>

      <Bubble
        from="owner"
        time="23:42"
        className="max-w-100 p-1.5 pb-2.5 sm:max-w-100"
        rowClassName="mt-7 motion-safe:animate-rise motion-safe:[animation-delay:.8s]"
        timeClassName="mr-2.5"
      >
        <Image
          src={oakTable}
          alt="Foto de una mesa redonda de roble en un comedor luminoso, mandada desde el celular"
          sizes="(min-width: 640px) 390px, 85vw"
          placeholder="blur"
          preload
          className="h-75 w-full rounded-[22px] rounded-tr-sm object-cover object-[50%_80%]"
        />
        <p className="mx-3 mt-2.5">Por fin está lista la mesa nueva de roble. ¿La podés publicar para el finde?</p>
      </Bubble>

      <div className="motion-safe:animate-rise motion-safe:[animation-delay:1.05s]">
        <ApprovalDemo />
      </div>
    </section>
  );
}
