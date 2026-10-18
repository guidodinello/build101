import Image from "next/image";
import { CheckIcon } from "lucide-react";
import { ApprovalDemo } from "@/components/landing/approval-demo";
import { Bubble, DayChip, Display } from "@/components/landing/chat";
import { CtaLink } from "@/components/landing/cta-link";
import oakTable from "@/components/landing/photos/oak-table.jpg";

const PROMISES = ["No app to install", "You approve every post", "Speaks your Spanish"];

export function Hero() {
  return (
    <section aria-labelledby="hero-title">
      <DayChip className="mt-6 motion-safe:animate-rise sm:mt-6">Today</DayChip>

      <Bubble
        from="neitor"
        time="11:41 PM"
        className="px-6 pt-6 pb-4 sm:max-w-[92%] sm:px-8.5 sm:pt-7.5"
        rowClassName="motion-safe:animate-rise motion-safe:[animation-delay:.05s]"
      >
        <Display as="h1" id="hero-title" className="text-[clamp(2.6rem,6vw,5.6rem)] leading-[0.95]">
          Hi, I&apos;m Neitor. Your marketing agency, living in your WhatsApp.
        </Display>
      </Bubble>

      <Bubble
        from="neitor"
        time="11:41 PM"
        className="px-6 pt-5 sm:max-w-[68%] sm:text-xl"
        rowClassName="motion-safe:animate-rise motion-safe:[animation-delay:.35s]"
      >
        <p className="mb-4.5 text-pretty">
          Send me a photo of what you sell. My team plans it, writes it, designs it and posts it to your Instagram.{" "}
          <strong>Nothing goes out until you tap Approve.</strong>
        </p>
        <div className="flex flex-wrap gap-2.5">
          <CtaLink icon>Get started on WhatsApp</CtaLink>
          <CtaLink href="#how" variant="soft">
            See how it works
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
        time="11:42 PM"
        className="max-w-100 p-1.5 pb-2.5 sm:max-w-100"
        rowClassName="mt-7 motion-safe:animate-rise motion-safe:[animation-delay:.8s]"
        timeClassName="mr-2.5"
      >
        <Image
          src={oakTable}
          alt="Photo of a round oak table in a bright dining room, sent from the owner's phone"
          sizes="(min-width: 640px) 390px, 85vw"
          placeholder="blur"
          preload
          className="h-75 w-full rounded-[22px] rounded-tr-sm object-cover object-[50%_80%]"
        />
        <p className="mx-3 mt-2.5">The new oak table is finally ready. Can you post it for the weekend?</p>
      </Bubble>

      <div className="motion-safe:animate-rise motion-safe:[animation-delay:1.05s]">
        <ApprovalDemo />
      </div>
    </section>
  );
}
