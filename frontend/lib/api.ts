const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type BusinessInfo = {
  name: string | null;
  category: string | null;
  one_liner: string | null;
  description: string | null;
  location: string | null;
  website: string | null;
  instagram_handle: string | null;
};

export type Product = {
  id: string;
  name: string;
  description: string;
  price: string | null;
  category: string | null;
  position: number;
  asset_count: number;
  archived: boolean;
};

export type AssetKind = "logo" | "photo" | "video";

export type Asset = {
  id: string;
  kind: AssetKind;
  status: "uploading" | "ready" | "failed";
  url: string;
  thumbnail_url: string | null;
  width: number | null;
  height: number | null;
  duration_ms: number | null;
  derived_from_asset_id: string | null;
  owner_hint: string | null;
  palette: string[] | null;
  product_ids: string[];
  reel_suitable: boolean | null;
  analyzed: boolean;
  archived: boolean;
};

export type Goal = "sales" | "awareness" | "launch" | "loyalty";
export type EmojiPolicy = "many" | "few" | "none";
export type Scale = 1 | 2 | 3 | 4 | 5;
export type PostsPerWeek = 2 | 3 | 5;

export type Questionnaire = {
  goal: Goal;
  audiences: string[];
  formality: Scale;
  humor: Scale;
  posts_per_week: PostsPerWeek;
  emoji_policy: EmojiPolicy;
  avoid: string | null;
  current_offer: string | null;
};

export type InstagramStatus = "not_connected" | "pending" | "connected" | "error";

export type OnboardingState = {
  business: BusinessInfo;
  products: Product[];
  brand: { three_words: string[]; colors: string[] };
  assets: Asset[];
  preferences: Questionnaire | null;
  instagram: { status: InstagramStatus; handle: string | null };
  completed: boolean;
  whatsapp_url: string;
};

export type BusinessInput = {
  name: string;
  category: string;
  one_liner: string;
  description?: string;
  location: string;
  website?: string;
  instagram_handle?: string;
};

export type ProductInput = {
  id?: string;
  name: string;
  description: string;
  price?: string;
  category?: string;
  asset_ids?: string[];
};

export type BrandInput = {
  three_words: [string, string, string];
  colors: string[];
  no_brand_yet?: boolean;
};

export type UploadRequest = {
  kind: AssetKind;
  filename: string;
  content_type: string;
  size_bytes: number;
  owner_hint?: string;
};

export type UploadTicket = {
  asset_id: string;
  upload_url: string;
  upload_token: string;
  resumable: boolean;
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }

  get isLinkInvalid() {
    return [401, 403, 404, 410].includes(this.status);
  }
}

const GENERIC_ERROR = "Algo salió mal. Probá de nuevo en un ratito.";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      cache: "no-store",
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "network_error", "No pudimos conectarnos. Revisá tu conexión.");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      body?.error?.code ?? "unknown",
      body?.error?.message ?? GENERIC_ERROR,
    );
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const onboarding = (token: string) => `/api/o/${encodeURIComponent(token)}`;

export const onboardingApi = {
  getState: (token: string) => request<OnboardingState>(onboarding(token)),

  saveBusiness: (token: string, body: BusinessInput) =>
    request<OnboardingState>(`${onboarding(token)}/business`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  saveProducts: (token: string, products: ProductInput[]) =>
    request<OnboardingState>(`${onboarding(token)}/products`, {
      method: "PUT",
      body: JSON.stringify({ products }),
    }),

  saveBrand: (token: string, body: BrandInput) =>
    request<OnboardingState>(`${onboarding(token)}/brand`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  savePreferences: (token: string, body: Questionnaire) =>
    request<OnboardingState>(`${onboarding(token)}/preferences`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  requestUpload: (token: string, body: UploadRequest) =>
    request<UploadTicket>(`${onboarding(token)}/uploads`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  completeUpload: (token: string, assetId: string) =>
    request<Asset>(`${onboarding(token)}/assets/${assetId}/complete`, { method: "POST" }),

  deleteAsset: (token: string, assetId: string) =>
    request<void>(`${onboarding(token)}/assets/${assetId}`, { method: "DELETE" }),

  connectInstagram: (token: string) =>
    request<{ auth_url: string }>(`${onboarding(token)}/instagram/connect`, {
      method: "POST",
      body: "{}",
    }),

  complete: (token: string) =>
    request<{ status: string }>(`${onboarding(token)}/complete`, { method: "POST" }),
};

export function messageOf(error: unknown) {
  return error instanceof ApiError ? error.message : GENERIC_ERROR;
}
