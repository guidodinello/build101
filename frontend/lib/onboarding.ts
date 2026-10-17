import type { OnboardingState } from "@/lib/api";

export const STEPS = [
  "business",
  "products",
  "brand",
  "photos",
  "preferences",
  "instagram",
] as const;

export type Step = (typeof STEPS)[number] | "done";

export const MIN_PHOTOS = 3;
export const MAX_PHOTOS = 15;
export const MAX_PRODUCTS = 5;

export function isStep(value: unknown): value is Step {
  return value === "done" || STEPS.includes(value as (typeof STEPS)[number]);
}

export function readyPhotos(state: OnboardingState) {
  return state.assets.filter(
    (asset) => asset.kind === "photo" && asset.status === "ready" && !asset.archived,
  );
}

export function currentLogo(state: OnboardingState) {
  return state.assets.find(
    (asset) => asset.kind === "logo" && asset.status === "ready" && !asset.archived,
  );
}

export const atHandle = (handle: string) => `@${handle.replace(/^@+/, "")}`;

export function resumeStep(state: OnboardingState): Step {
  if (state.completed) return "done";
  const { business } = state;
  if (!business.name || !business.category || !business.one_liner) return "business";
  if (state.products.filter((product) => !product.archived).length === 0) return "products";
  if (state.brand.three_words.length < 3) return "brand";
  if (readyPhotos(state).length < MIN_PHOTOS) return "photos";
  if (!state.preferences) return "preferences";
  return "instagram";
}
