import type { LucideIcon } from "lucide-react";
import { CalendarDaysIcon, ImageIcon, PenLineIcon, SendIcon } from "lucide-react";
import { Bubble, DayChip, Display, Label } from "@/components/landing/chat";
import { NeitorAvatar } from "@/components/landing/site-header";
import { cn } from "@/lib/utils";

const SPECIALISTS: { role: string; job: string; icon: LucideIcon }[] = [
  { role: "Strategist", job: "Plans your week around what you sell and the dates that matter.", icon: CalendarDaysIcon },
  { role: "Copywriter", job: "Writes captions in your voice, in your Spanish.", icon: PenLineIcon },
  { role: "Art director", job: "Turns your real photos into on-brand posts. Never alters your product.", icon: ImageIcon },
  { role: "Publisher", job: "Posts or schedules on Instagram, only after you approve.", icon: SendIcon },
];

const TRACE = [
  { who: "Strategist", what: "shelves are a best seller, and it's Friday: lead with the weekend." },
  { who: "Copywriter", what: "short, warm, the 10% up front, no hard sell." },
  { who: "Art director", what: "three framings of your photo in walnut, sand and moss." },
  { who: "You", what: "picked option 2, tapped Approve.", owner: true },
  { who: "Publisher", what: "scheduled for Saturday 10:00." },
];

export function TeamSection() {
  return (
    <section aria-labelledby="team-title">
      <DayChip id="team">Who&apos;s behind Neitor</DayChip>
      <Bubble
        from="neitor"
        time="6:36 PM"
        className="px-6 pt-6 pb-4 sm:max-w-[92%] sm:px-8.5 sm:pt-7.5"
        rowClassName="motion-safe:reveal-on-scroll"
      >
        <Display as="h2" id="team-title" className="text-[clamp(2.1rem,4.4vw,3.75rem)] leading-none">
          You only ever talk to me. Behind me, a whole team works on every post.
        </Display>
        <div className="mt-7 flex flex-wrap gap-7">
          <ul className="flex flex-[1_1_320px] flex-col gap-4.5">
            <li className="flex gap-3.5">
              <NeitorAvatar className="size-11.5 text-lg" />
              <div>
                <strong>Account manager</strong> <Label className="ml-1 text-ld-accent-ink">that&apos;s me</Label>
                <p className="text-base text-ld-muted">Talks with you, understands what you need, runs the team.</p>
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
            <Label className="mb-4 block">How the weekend promo got made</Label>
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
