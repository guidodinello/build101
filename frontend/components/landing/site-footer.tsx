import { CtaLink } from "@/components/landing/cta-link";
import { NeitorAvatar } from "@/components/landing/site-header";
import { WHATSAPP_START_URL } from "@/lib/whatsapp";

const PRODUCT_LINKS = [
  { href: "#how", label: "Cómo funciona" },
  { href: "#team", label: "El equipo" },
  { href: "#control", label: "Vos tenés el control" },
  { href: "#pricing", label: "Precios" },
  { href: "#faq", label: "Preguntas" },
];

const linkClass = "text-[15px] text-[#dce8e1] transition-colors hover:text-white";

export function SiteFooter() {
  return (
    <footer className="mt-28 rounded-t-[40px] bg-ld-ink text-ld-on-dark-muted">
      <div className="mx-auto max-w-280 px-6 pt-18 pb-8">
        <div className="flex flex-wrap gap-x-16 gap-y-12">
          <div className="flex flex-[2_1_300px] flex-col items-start gap-4">
            <div className="flex items-center gap-3">
              <NeitorAvatar className="size-11 bg-ld-on-dark text-[22px] text-ld-forest" />
              <span className="font-heading text-2xl font-extrabold tracking-tight text-white">Neitor AI</span>
            </div>
            <p className="max-w-85 text-base leading-normal">
              Una agencia de marketing con IA en tu WhatsApp. Vos aprobás, Neitor hace el resto.
            </p>
            <CtaLink icon className="mt-1.5">
              Empezá en WhatsApp
            </CtaLink>
          </div>
          <nav aria-label="Producto" className="flex flex-[1_1_160px] flex-col gap-3">
            <span className="mb-1 text-xs font-semibold tracking-[0.06em] text-[#7f9a8d] uppercase">Producto</span>
            {PRODUCT_LINKS.map((link) => (
              <a key={link.href} href={link.href} className={linkClass}>
                {link.label}
              </a>
            ))}
          </nav>
          <nav aria-label="Contacto" className="flex flex-[1_1_160px] flex-col gap-3">
            <span className="mb-1 text-xs font-semibold tracking-[0.06em] text-[#7f9a8d] uppercase">Contacto</span>
            <a href={WHATSAPP_START_URL} className={linkClass}>
              WhatsApp
            </a>
          </nav>
        </div>
        <p
          aria-hidden="true"
          className="mt-18 overflow-hidden text-center font-heading text-[clamp(4rem,15vw,12.5rem)] leading-[0.8] font-extrabold tracking-[-0.06em] whitespace-nowrap text-[#133528] select-none"
        >
          Neitor AI
        </p>
        <div className="mt-7 flex flex-wrap gap-x-7 gap-y-2.5 border-t border-white/10 pt-5.5 text-[13px] text-[#7f9a8d]">
          <span>© 2026 Neitor AI</span>
          <span className="sm:ml-auto">
            El negocio y los posts de ejemplo son ilustrativos. Fotos de Shixart1985 en{" "}
            <a
              href="https://commons.wikimedia.org/wiki/User:Shixart1985"
              className="underline underline-offset-2 hover:text-white"
            >
              Wikimedia Commons
            </a>
            , <a href="https://creativecommons.org/licenses/by/2.0/" className="underline underline-offset-2 hover:text-white">CC BY 2.0</a>.
          </span>
        </div>
      </div>
    </footer>
  );
}
