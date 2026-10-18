import { CtaLink } from "@/components/landing/cta-link";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { href: "#how", label: "How it works" },
  { href: "#team", label: "The team" },
  { href: "#pricing", label: "Pricing" },
  { href: "#faq", label: "FAQ" },
];

export function NeitorAvatar({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-10.5 shrink-0 items-center justify-center rounded-full bg-ld-forest font-heading text-[21px] font-extrabold text-ld-on-dark",
        className,
      )}
    >
      N
    </span>
  );
}

export function SiteHeader() {
  return (
    <header className="sticky top-3.5 z-10 px-4">
      <div className="mx-auto flex min-h-16 max-w-280 items-center gap-3.5 rounded-full bg-white/80 py-2.5 pr-2.5 pl-3 shadow-float backdrop-blur-md backdrop-saturate-150">
        <a href="#top" className="relative rounded-full outline-none focus-visible:ring-3 focus-visible:ring-ld-forest/60">
          <NeitorAvatar />
          <span
            aria-hidden="true"
            className="absolute -right-px -bottom-px size-3 rounded-full bg-green-500 ring-[2.5px] ring-white"
          />
          <span className="sr-only">Neitor AI, back to top</span>
        </a>
        <div className="mr-auto flex min-w-0 flex-col gap-0.5">
          <span className="font-heading text-lg leading-tight font-extrabold tracking-tight">Neitor AI</span>
          <span className="truncate text-[13px] leading-tight font-medium text-ld-subtle">
            your marketing team · online
          </span>
        </div>
        <nav aria-label="Main" className="flex items-center gap-6.5">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="hidden text-[15px] font-semibold text-[#2d4a3e] transition-colors hover:text-ld-ink md:inline"
            >
              {link.label}
            </a>
          ))}
          <CtaLink size="sm" className="whitespace-nowrap">
            Get started
          </CtaLink>
        </nav>
      </div>
    </header>
  );
}
