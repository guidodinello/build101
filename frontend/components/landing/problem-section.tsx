import { Bubble, DayChip, Display } from "@/components/landing/chat";
import { cn } from "@/lib/utils";

const PAINS = [
  "I know social media sells. I just don't have time to plan, write and design posts every week.",
  "An agency or a community manager costs more than I can justify.",
  "Canva, Meta Business Suite, ChatGPT… I still end up at the computer doing it all myself.",
  "So I post when I can. My Instagram looks abandoned.",
];

const VALUES = [
  { title: "Zero learning curve", body: "Everything happens in a WhatsApp chat. Text, photos, voice notes." },
  { title: "It knows your brand", body: "Your tone, colors, products and customers shape every post." },
  { title: "A team, not a tool", body: "Strategy, copy, design and publishing, coordinated for you." },
  { title: "You stay in control", body: "Nothing is published without your explicit Approve.", highlight: true },
];

export function ProblemSection() {
  return (
    <section aria-labelledby="why-title">
      <DayChip id="why">Sound familiar?</DayChip>
      {PAINS.map((pain) => (
        <Bubble key={pain} from="owner" className="sm:text-[22px]" rowClassName="motion-safe:reveal-on-scroll">
          {pain}
        </Bubble>
      ))}

      <Bubble
        from="neitor"
        time="8:02 AM"
        className="px-6 pt-6 pb-4 sm:max-w-[92%] sm:px-8.5 sm:pt-7.5"
        rowClassName="mt-6.5 motion-safe:reveal-on-scroll"
      >
        <Display as="h2" id="why-title" className="text-[clamp(2.1rem,4.4vw,3.75rem)] leading-none">
          You don&apos;t need another app to learn. You need someone who does it, the way you would.
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
