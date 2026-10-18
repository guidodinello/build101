import Image from "next/image";
import { CheckIcon, ClipboardListIcon, PlayIcon } from "lucide-react";
import { Bubble, DayChip, Label, Timestamp } from "@/components/landing/chat";
import { cn } from "@/lib/utils";
import oakTable from "@/components/landing/photos/oak-table.jpg";
import workshopHands from "@/components/landing/photos/workshop-hands.jpg";
import workshop from "@/components/landing/photos/workshop.jpg";

const BRAND_COLORS = [
  { name: "Walnut", hex: "#6b3e26" },
  { name: "Sand", hex: "#e9dcc6" },
  { name: "Moss", hex: "#4b5d3a" },
];

const WAVEFORM = [6, 14, 22, 10, 18, 8, 24, 12, 4, 16, 10, 20, 8, 14, 6, 18, 10, 4, 12, 6, 8, 4];

const OPTIONS = [
  { photo: workshop, alt: "Option 1, the workshop", frame: "bg-[#e9dcc6]", position: "object-center" },
  { photo: workshopHands, alt: "Option 2, hands at work on a plank", frame: "bg-[#6b3e26]", position: "object-center", picked: true },
  { photo: oakTable, alt: "Option 3, the oak table", frame: "bg-[#4b5d3a]", position: "object-[50%_85%]" },
];

export function HowItWorks() {
  return (
    <section aria-labelledby="how-title">
      <DayChip id="how" headingId="how-title">
        How it works · Monday
      </DayChip>

      <Bubble from="owner" time="9:02 AM" rowClassName="motion-safe:reveal-on-scroll">
        Hi
      </Bubble>
      <Bubble from="neitor" time="9:02 AM" className="sm:max-w-115" rowClassName="motion-safe:reveal-on-scroll">
        Welcome! First, tell me about your business. It takes about 5 minutes:
        <div className="mt-3 flex items-center gap-3.5 rounded-[18px] bg-ld-mist p-3">
          <span aria-hidden="true" className="flex size-14 shrink-0 items-center justify-center rounded-[14px] bg-ld-forest text-ld-on-dark">
            <ClipboardListIcon className="size-6" />
          </span>
          <span className="flex flex-col gap-0.5">
            <span className="text-base font-bold">Tell us about your business</span>
            <span className="text-sm text-ld-muted">Products, logo, a few photos, how you sound.</span>
            <span className="text-[13px] text-ld-subtle">neitor.ai</span>
          </span>
        </div>
      </Bubble>

      <Bubble from="neitor" className="px-0 pt-4 pb-0 sm:max-w-135" rowClassName="motion-safe:reveal-on-scroll">
        <p className="px-5">Here&apos;s what I understood about your brand. Did I get it right?</p>
        <dl className="mx-3.5 mt-3.5 grid grid-cols-[104px_1fr] gap-3.5 rounded-[18px] bg-ld-mist p-4.5 text-[15px] sm:grid-cols-[116px_1fr]">
          <dt><Label>Voice</Label></dt>
          <dd>Warm, proud of the craft, never pushy</dd>
          <dt className="pt-1.5"><Label>Colors</Label></dt>
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
          <dt><Label>Best sellers</Label></dt>
          <dd>Round oak table · Lapacho shelf · Bench</dd>
          <dt><Label>Talks about</Label></dt>
          <dd>New pieces · the workshop · caring for wood</dd>
        </dl>
        <Timestamp time="9:09 AM" className="px-4" />
        <div className="mt-2 flex text-base font-bold" aria-hidden="true">
          <span className="flex min-h-13 flex-1 items-center justify-center border-t border-ld-line text-ld-forest">Yes, that&apos;s us</span>
          <span className="flex min-h-13 flex-1 items-center justify-center border-t border-l border-ld-line text-ld-forest">Adjust</span>
        </div>
      </Bubble>

      <DayChip className="mt-14 sm:mt-14">Friday</DayChip>
      <Bubble from="owner" time="6:31 PM" className="min-w-75" rowClassName="motion-safe:reveal-on-scroll">
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
            <span className="sr-only">Voice note, </span>0:07
          </span>
        </div>
        <p className="mt-2.5 text-[15px] text-[#cfe0d7] italic">&ldquo;Make a post for the weekend promo, 10% off shelves.&rdquo;</p>
      </Bubble>

      <Bubble from="neitor" time="6:33 PM" className="sm:max-w-145" rowClassName="motion-safe:reveal-on-scroll">
        Got your voice note. Three options from your photos. Pick the one you like:
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
                {option.picked ? `${index + 1} · picked` : index + 1}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-[15px] text-ld-muted">Nothing is public until you approve.</p>
      </Bubble>
      <Bubble from="owner" time="6:35 PM" rowClassName="motion-safe:reveal-on-scroll">
        The second one. <strong>Approve</strong>
      </Bubble>
      <Bubble from="neitor" time="6:35 PM" rowClassName="motion-safe:reveal-on-scroll">
        <span className="inline-flex items-center gap-2">
          <CheckIcon className="size-4.5 text-green-600" strokeWidth={2.6} aria-hidden="true" />
          <span>
            Scheduled for <strong>Saturday 10:00</strong> on Instagram.
          </span>
        </span>
      </Bubble>
    </section>
  );
}
