"use client";

import { useCallback, useState, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import type { Asset, OnboardingState } from "@/lib/api";
import { isStep, resumeStep, type Step } from "@/lib/onboarding";
import { WizardContext } from "@/components/onboarding/wizard-context";
import { usePhotoUploads } from "@/components/onboarding/use-photo-uploads";
import { BusinessStep } from "@/components/onboarding/steps/business-step";
import { ProductsStep } from "@/components/onboarding/steps/products-step";
import { BrandStep } from "@/components/onboarding/steps/brand-step";
import { PhotosStep } from "@/components/onboarding/steps/photos-step";
import { PreferencesStep } from "@/components/onboarding/steps/preferences-step";
import { InstagramStep } from "@/components/onboarding/steps/instagram-step";
import { DoneScreen } from "@/components/onboarding/done-screen";

const SCREENS: Record<Step, () => ReactNode> = {
  business: BusinessStep,
  products: ProductsStep,
  brand: BrandStep,
  photos: PhotosStep,
  preferences: PreferencesStep,
  instagram: InstagramStep,
  done: DoneScreen,
};

type OnboardingWizardProps = {
  token: string;
  initialState: OnboardingState;
};

export function OnboardingWizard({ token, initialState }: OnboardingWizardProps) {
  const [state, setState] = useState(initialState);
  const searchParams = useSearchParams();
  const requested = searchParams.get("step");
  const requestedStep = isStep(requested) ? requested : resumeStep(state);
  const step: Step = state.completed
    ? "done"
    : requestedStep === "instagram" && !state.instagram_allowed
      ? "products"
      : requestedStep;

  const upsertAsset = useCallback((asset: Asset) => {
    setState((current) => ({
      ...current,
      assets: [...current.assets.filter((item) => item.id !== asset.id), asset],
    }));
  }, []);

  const photoUploads = usePhotoUploads(token, upsertAsset);

  const goTo = useCallback((next: Step) => {
    window.history.pushState(null, "", `?step=${next}`);
    window.scrollTo({ top: 0 });
  }, []);

  const Screen = SCREENS[step];

  return (
    <WizardContext value={{ token, state, setState, upsertAsset, goTo, photoUploads }}>
      <Screen key={step} />
    </WizardContext>
  );
}
