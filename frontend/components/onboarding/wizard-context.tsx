"use client";

import { createContext, use, type Dispatch, type SetStateAction } from "react";
import type { Asset, OnboardingState } from "@/lib/api";
import type { Step } from "@/lib/onboarding";
import type { PhotoUploads } from "@/components/onboarding/use-photo-uploads";

type WizardContextValue = {
  token: string;
  state: OnboardingState;
  setState: Dispatch<SetStateAction<OnboardingState>>;
  upsertAsset: (asset: Asset) => void;
  goTo: (step: Step) => void;
  photoUploads: PhotoUploads;
};

export const WizardContext = createContext<WizardContextValue | null>(null);

export function useWizard() {
  const context = use(WizardContext);
  if (!context) throw new Error("useWizard must be used inside OnboardingWizard");
  return context;
}
