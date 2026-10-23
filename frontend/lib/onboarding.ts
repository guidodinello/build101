import type { OnboardingState } from "@/lib/api";

export const STEPS = [
  "business",
  "instagram",
  "products",
  "photos",
  "brand",
  "preferences",
] as const;

export type WizardStepId = (typeof STEPS)[number];
export type Step = WizardStepId | "done";

export const MIN_PHOTOS = 3;
export const MAX_PHOTOS = 15;
export const MAX_PRODUCTS = 5;
export const MAX_PRODUCT_PHOTOS = 5;
export const MAX_BRAND_WORDS = 3;

export function isStep(value: unknown): value is Step {
  return value === "done" || STEPS.includes(value as WizardStepId);
}

export function readyPhotos(state: OnboardingState) {
  return state.assets.filter(
    (asset) => asset.kind === "photo" && asset.status === "ready" && !asset.archived,
  );
}

export function ownPhotos(state: OnboardingState) {
  return readyPhotos(state).filter((asset) => asset.source === "web");
}

export function instagramPhotos(state: OnboardingState) {
  return readyPhotos(state).filter((asset) => asset.source === "instagram");
}

export function currentLogo(state: OnboardingState) {
  return state.assets.find(
    (asset) => asset.kind === "logo" && asset.status === "ready" && !asset.archived,
  );
}

export const atHandle = (handle: string) => `@${handle.replace(/^@+/, "")}`;

export function isInstagramConnected(state: OnboardingState) {
  return state.instagram.status === "connected";
}

export function resumeStep(state: OnboardingState): Step {
  if (state.completed) return "done";
  const { business } = state;
  if (!business.name || !business.category || !business.one_liner) return "business";
  if (state.products.filter((product) => !product.archived).length === 0) {
    return isInstagramConnected(state) || !state.instagram_allowed ? "products" : "instagram";
  }
  if (readyPhotos(state).length < MIN_PHOTOS) return "photos";
  if (state.brand.three_words.length === 0) return "brand";
  return "preferences";
}
