import * as z from "zod";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const BusinessInfoSchema = z.object({
  name: z.string().nullable(),
  category: z.string().nullable(),
  one_liner: z.string().nullable(),
  description: z.string().nullable(),
  location: z.string().nullable(),
  website: z.string().nullable(),
  instagram_handle: z.string().nullable(),
});
export type BusinessInfo = z.infer<typeof BusinessInfoSchema>;

const ProductSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  price: z.string().nullable(),
  category: z.string().nullable(),
  position: z.number(),
  asset_count: z.number(),
  archived: z.boolean(),
});
export type Product = z.infer<typeof ProductSchema>;

const AssetKindSchema = z.literal(["logo", "photo", "video"]);
export type AssetKind = z.infer<typeof AssetKindSchema>;
const AssetSourceSchema = z.literal(["web", "instagram"]);
export type AssetSource = z.infer<typeof AssetSourceSchema>;

const AssetSchema = z.object({
  id: z.string(),
  kind: AssetKindSchema,
  source: AssetSourceSchema,
  status: z.literal(["uploading", "ready", "failed"]),
  url: z.string(),
  thumbnail_url: z.string().nullable(),
  width: z.number().nullable(),
  height: z.number().nullable(),
  duration_ms: z.number().nullable(),
  derived_from_asset_id: z.string().nullable(),
  owner_hint: z.string().nullable(),
  palette: z.array(z.string()).nullable(),
  product_ids: z.array(z.string()),
  reel_suitable: z.boolean().nullable(),
  analyzed: z.boolean(),
  archived: z.boolean(),
});
export type Asset = z.infer<typeof AssetSchema>;

const GoalSchema = z.literal(["sales", "awareness", "launch", "loyalty"]);
export type Goal = z.infer<typeof GoalSchema>;
const EmojiPolicySchema = z.literal(["many", "few", "none"]);
export type EmojiPolicy = z.infer<typeof EmojiPolicySchema>;
const ScaleSchema = z.literal([1, 2, 3, 4, 5]);
export type Scale = z.infer<typeof ScaleSchema>;
const PostsPerWeekSchema = z.literal([2, 3, 5]);
export type PostsPerWeek = z.infer<typeof PostsPerWeekSchema>;

const QuestionnaireSchema = z.object({
  goal: GoalSchema,
  audiences: z.array(z.string()),
  formality: ScaleSchema.nullable(),
  humor: ScaleSchema.nullable(),
  posts_per_week: PostsPerWeekSchema.nullable(),
  emoji_policy: EmojiPolicySchema.nullable(),
  avoid: z.string().nullable(),
  current_offer: z.string().nullable(),
});
export type Questionnaire = z.infer<typeof QuestionnaireSchema>;

const InstagramStatusSchema = z.literal(["not_connected", "pending", "connected", "error"]);
export type InstagramStatus = z.infer<typeof InstagramStatusSchema>;

const OnboardingStateSchema = z.object({
  business: BusinessInfoSchema,
  products: z.array(ProductSchema),
  brand: z.object({ three_words: z.array(z.string()), colors: z.array(z.string()) }),
  assets: z.array(AssetSchema),
  preferences: QuestionnaireSchema.nullable(),
  instagram: z.object({
    status: InstagramStatusSchema,
    handle: z.string().nullable(),
    // Defaults to true for a backend from before INSTAGRAM=off, which always offered it.
    available: z.boolean().default(true),
  }),
  completed: z.boolean(),
  whatsapp_url: z.string(),
});
export type OnboardingState = z.infer<typeof OnboardingStateSchema>;

const UploadTicketSchema = z.object({
  asset_id: z.string(),
  upload_url: z.string(),
  upload_token: z.string(),
  resumable: z.boolean(),
});
export type UploadTicket = z.infer<typeof UploadTicketSchema>;

const ConnectResponseSchema = z.object({ auth_url: z.string() });
export type ConnectResponse = z.infer<typeof ConnectResponseSchema>;

const CompleteResponseSchema = z.object({ status: z.literal("generating_brand") });
export type CompleteResponse = z.infer<typeof CompleteResponseSchema>;

const ErrorBodySchema = z.object({
  error: z.object({ code: z.string().optional(), message: z.string().optional() }).optional(),
});

export type BusinessInput = {
  name: string;
  category: string;
  one_liner: string;
  location?: string | undefined;
};

export type ProductInput = {
  id?: string | undefined;
  name: string;
  description: string;
  price?: string | undefined;
  category?: string;
  asset_ids?: string[];
};

export type BrandInput = {
  three_words: string[];
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

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    options?: ErrorOptions,
  ) {
    super(message, options);
  }

  get isLinkInvalid() {
    return [401, 403, 404, 410].includes(this.status);
  }
}

const GENERIC_ERROR = "Algo salió mal. Probá de nuevo en un ratito.";

async function send(path: string, init?: RequestInit): Promise<Response> {
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
    const body = ErrorBodySchema.safeParse(await response.json().catch(() => null));
    const error = body.success ? body.data.error : undefined;
    throw new ApiError(response.status, error?.code ?? "unknown", error?.message ?? GENERIC_ERROR);
  }
  return response;
}

// A body that does not match the schema means the backend contract changed: fail here, with the
// same ApiError the callers already handle, instead of crashing later inside a component.
async function request<S extends z.ZodType>(
  schema: S,
  path: string,
  init?: RequestInit,
): Promise<z.infer<S>> {
  const response = await send(path, init);
  const body = schema.safeParse(await response.json().catch(() => null));
  if (!body.success) {
    throw new ApiError(response.status, "invalid_response", GENERIC_ERROR, { cause: body.error });
  }
  return body.data;
}

const onboarding = (token: string) => `/api/o/${encodeURIComponent(token)}`;

export const onboardingApi = {
  getState: (token: string) => request(OnboardingStateSchema, onboarding(token)),

  saveBusiness: (token: string, body: BusinessInput) =>
    request(OnboardingStateSchema, `${onboarding(token)}/business`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  saveProducts: (token: string, products: ProductInput[]) =>
    request(OnboardingStateSchema, `${onboarding(token)}/products`, {
      method: "PUT",
      body: JSON.stringify({ products }),
    }),

  saveBrand: (token: string, body: BrandInput) =>
    request(OnboardingStateSchema, `${onboarding(token)}/brand`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  savePreferences: (token: string, body: Questionnaire) =>
    request(OnboardingStateSchema, `${onboarding(token)}/preferences`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  requestUpload: (token: string, body: UploadRequest) =>
    request(UploadTicketSchema, `${onboarding(token)}/uploads`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  completeUpload: (token: string, assetId: string) =>
    request(AssetSchema, `${onboarding(token)}/assets/${assetId}/complete`, { method: "POST" }),

  deleteAsset: async (token: string, assetId: string) => {
    await send(`${onboarding(token)}/assets/${assetId}`, { method: "DELETE" });
  },

  connectInstagram: (token: string) =>
    request(ConnectResponseSchema, `${onboarding(token)}/instagram/connect`, {
      method: "POST",
      body: "{}",
    }),

  complete: (token: string) =>
    request(CompleteResponseSchema, `${onboarding(token)}/complete`, { method: "POST" }),
};

export function messageOf(error: unknown) {
  return error instanceof ApiError ? error.message : GENERIC_ERROR;
}
