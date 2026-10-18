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
  title: "Neitor AI · Your marketing agency in WhatsApp",
  description:
    "Send a photo of what you sell. Neitor's AI team plans, writes, designs and posts it to your Instagram. Nothing goes out until you tap Approve.",
  openGraph: {
    title: "Neitor AI · Your marketing agency in WhatsApp",
    description: "You approve, Neitor does the rest. An AI marketing agency that lives in your WhatsApp.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#f2f5f1",
};

export default function Home() {
  return (
    <div id="top" lang="en" className="flex-1 bg-ld-ground bg-dot-grid text-ld-ink">
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
