import { LockIcon } from "lucide-react";
import { Display } from "@/components/landing/chat";

const PROMISES = [
  { title: "Every post comes to you first", body: "A preview with the caption, right in the chat." },
  { title: "We never ask for your password", body: "You connect Instagram on Instagram's own page." },
  { title: "Your real products, untouched", body: "Posts start from your photos. The product is never altered." },
];

export function ControlSection() {
  return (
    <section
      id="control"
      aria-labelledby="control-title"
      className="mt-30 scroll-mt-28 rounded-[36px] bg-ld-forest px-6 py-12 text-center text-ld-on-dark shadow-panel motion-safe:reveal-on-scroll sm:px-11"
    >
      <span aria-hidden="true" className="inline-flex size-15 items-center justify-center rounded-full bg-ld-accent text-ld-ink">
        <LockIcon className="size-7" />
      </span>
      <Display as="h2" id="control-title" className="mx-auto mt-4.5 max-w-190 text-[clamp(2.2rem,5vw,4.25rem)] leading-[0.98]">
        Nothing is published without your Approve.
      </Display>
      <ul className="mt-8.5 grid gap-3 text-left text-base leading-snug md:grid-cols-3">
        {PROMISES.map((promise) => (
          <li key={promise.title} className="rounded-[20px] bg-white/7 px-5 py-4.5 shadow-[inset_0_0_0_1px_rgb(255_255_255/0.08)]">
            <strong className="mb-1 block text-white">{promise.title}</strong>
            <span className="text-ld-on-dark-muted">{promise.body}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
