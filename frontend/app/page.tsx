import type { Metadata, Viewport } from "next";
import { ComparisonSection } from "@/components/landing/comparison-section";
import { ControlSection } from "@/components/landing/control-section";
import { FaqSection } from "@/components/landing/faq-section";
import { FinalCta } from "@/components/landing/final-cta";
import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { PricingSection } from "@/components/landing/pricing-section";
import { ProblemSection } from "@/components/landing/problem-section";
import { SiteFooter } from "@/components/landing/site-footer";
import { SiteHeader } from "@/components/landing/site-header";
import { TeamSection } from "@/components/landing/team-section";

export const metadata: Metadata = {
  title: "Neitor AI · Tu agencia de marketing en WhatsApp",
  description:
    "Mandá una foto de lo que vendés. El equipo de IA de Neitor planifica el post, lo escribe, lo diseña y lo publica en tu Instagram. Nada sale hasta que tocás Aprobar.",
  openGraph: {
    title: "Neitor AI · Tu agencia de marketing en WhatsApp",
    description: "Vos aprobás, Neitor hace el resto. Una agencia de marketing con IA que vive en tu WhatsApp.",
    type: "website",
    locale: "es_UY",
  },
};

export const viewport: Viewport = {
  themeColor: "#f2f5f1",
};

export default function Home() {
  return (
    <div id="top" className="flex-1 bg-ld-ground bg-dot-grid text-ld-ink">
      <SiteHeader />
      <main className="mx-auto max-w-240 px-4 pt-11 sm:px-6">
        <Hero />
        <ProblemSection />
        <HowItWorks />
        <TeamSection />
        <ControlSection />
        <ComparisonSection />
        <PricingSection />
        <FaqSection />
        <FinalCta />
      </main>
      <SiteFooter />
    </div>
  );
}
