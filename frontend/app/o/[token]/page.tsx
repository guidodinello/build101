import type { Metadata } from "next";
import { ExpiredLink } from "@/components/onboarding/expired-link";
import { OnboardingWizard } from "@/components/onboarding/wizard";
import { ApiError, onboardingApi, type OnboardingState } from "@/lib/api";

export const metadata: Metadata = {
  title: "Tu negocio · Neitor AI",
  robots: { index: false },
};

async function loadState(token: string): Promise<OnboardingState | null> {
  try {
    return await onboardingApi.getState(token);
  } catch (error) {
    if (error instanceof ApiError && error.isLinkInvalid) return null;
    throw error;
  }
}

export default async function OnboardingPage({ params }: PageProps<"/o/[token]">) {
  const { token } = await params;
  const state = await loadState(token);
  if (!state) return <ExpiredLink />;
  return <OnboardingWizard token={token} initialState={state} />;
}
