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
      <span className={muted}> / month</span>
    </span>
  );
}

export function PricingSection() {
  return (
    <section aria-labelledby="pricing-title">
      <DayChip id="pricing" headingId="pricing-title">
        Launch pricing
      </DayChip>
      <Bubble from="neitor" time="6:40 PM" rowClassName="motion-safe:reveal-on-scroll">
        Try me free. When you want more, pick a plan, billed monthly.
      </Bubble>
      <ul className="mt-3 grid gap-3.5 motion-safe:reveal-on-scroll md:grid-cols-3">
        <Plan
          name="Free"
          price={<Amount value="US$0" muted="text-ld-muted" />}
          action={<CtaLink variant="soft">Try it free</CtaLink>}
        >
          <li>Up to 3 posts or carousels a month</li>
          <li>Made from your photos</li>
          <li>Published to your Instagram</li>
          <li>No card needed</li>
        </Plan>
        <Plan
          name="Basic"
          badge="Recommended"
          dark
          price={<Amount value="US$29" muted="text-ld-sage" />}
          action={<CtaLink>Get started</CtaLink>}
        >
          <li>Posts and carousels from your photos</li>
          <li>A weekly content plan, on request</li>
          <li>Publish now or schedule on Instagram</li>
          <li>Every post approved by you, on WhatsApp</li>
        </Plan>
        <Plan
          name="Pro"
          price={<Amount value="US$49" muted="text-ld-muted" />}
          action={<CtaLink variant="soft">Join the Pro list</CtaLink>}
        >
          <li>Everything in Basic</li>
          <li>Replies to comments and DMs <Label>soon</Label></li>
          <li>Sale alerts on WhatsApp <Label>soon</Label></li>
          <li>A weekly results summary <Label>soon</Label></li>
        </Plan>
      </ul>
    </section>
  );
}
