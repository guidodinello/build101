import "server-only";
import oakTable from "@/components/landing/photos/oak-table.jpg";
import workshopHands from "@/components/landing/photos/workshop-hands.jpg";
import workshop from "@/components/landing/photos/workshop.jpg";
import type {
  Asset,
  BrandInput,
  BusinessInput,
  CompleteResponse,
  OnboardingState,
  ProductInput,
  Questionnaire,
  UploadRequest,
} from "@/lib/api";

const EXPIRED_TOKENS = new Set(["vencido", "expired"]);
const ANALYSIS_DELAY_MS = 4000;
const MOCK_PALETTE = ["#4f5d2f", "#c89b6d", "#f3ebdd"];
const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp", "image/heic"];
const MAX_PHOTO_BYTES = 10 * 1024 * 1024;
const INSTAGRAM_IMPORT_DELAY_MS = 6000;
const INSTAGRAM_PHOTOS = [oakTable.src, workshop.src, workshopHands.src];

type StoredAsset = Asset & { completedAt: number | null };
type StoredFile = { bytes: ArrayBuffer; contentType: string };
type MockBusiness = Omit<OnboardingState, "assets"> & { assets: StoredAsset[] };

type MockStore = { businesses: Map<string, MockBusiness>; files: Map<string, StoredFile> };

const globalStore = globalThis as typeof globalThis & { __onboardingMock?: MockStore };
const store = (globalStore.__onboardingMock ??= { businesses: new Map(), files: new Map() });

let nextId = 0;
const newId = (prefix: string) => `${prefix}_${Date.now().toString(36)}${(nextId++).toString(36)}`;

export class MockError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

function business(token: string): MockBusiness {
  if (EXPIRED_TOKENS.has(token)) throw new MockError(410, "link_expired", "Este link venció.");
  let found = store.businesses.get(token);
  if (!found) {
    found = {
      business: {
        name: "Muebles Ramírez",
        category: null,
        one_liner: null,
        description: null,
        location: null,
        website: null,
        instagram_handle: null,
      },
      products: [],
      brand: { three_words: [], colors: [] },
      assets: [],
      preferences: null,
      instagram: { status: "not_connected", handle: null, available: true },
      completed: false,
      whatsapp_url: process.env.NEXT_PUBLIC_WHATSAPP_URL ?? "https://wa.me/",
    };
    store.businesses.set(token, found);
  }
  return found;
}

function toAsset({ completedAt, ...asset }: StoredAsset): Asset {
  const analyzed = completedAt !== null && Date.now() - completedAt > ANALYSIS_DELAY_MS;
  return { ...asset, analyzed: asset.kind === "logo" || analyzed };
}

function snapshot(found: MockBusiness): OnboardingState {
  return { ...found, assets: found.assets.filter((asset) => !asset.archived).map(toAsset) };
}

function activePhotos(found: MockBusiness) {
  return found.assets.filter((asset) => asset.kind === "photo" && !asset.archived);
}

function webPhotos(found: MockBusiness) {
  return activePhotos(found).filter((asset) => asset.source === "web");
}

export function getState(token: string) {
  return snapshot(business(token));
}

export function saveBusiness(token: string, input: BusinessInput) {
  const found = business(token);
  found.business = {
    ...found.business,
    name: input.name,
    category: input.category,
    one_liner: input.one_liner,
    location: input.location ?? null,
  };
  return snapshot(found);
}

export function saveProducts(token: string, products: ProductInput[]) {
  if (products.length > 5) throw new MockError(422, "too_many_products", "Hasta 5 productos.");
  if (products.some((input) => (input.asset_ids ?? []).length > 5)) {
    throw new MockError(422, "too_many_product_photos", "Hasta 5 fotos por producto.");
  }
  const found = business(token);
  const linkedTo = new Map<string, string>();
  const kept = products.map((input, position) => {
    const id = input.id ?? newId("prod");
    for (const assetId of input.asset_ids ?? []) linkedTo.set(assetId, id);
    return {
      id,
      name: input.name,
      description: input.description,
      price: input.price ?? null,
      category: input.category ?? null,
      position,
      asset_count: 0,
      archived: false,
    };
  });
  const keptIds = new Set(kept.map((product) => product.id));
  const archived = found.products
    .filter((product) => !keptIds.has(product.id))
    .map((product) => ({ ...product, archived: true }));
  found.products = [...kept, ...archived];
  found.assets = found.assets.map((asset) => {
    const productId = linkedTo.get(asset.id);
    return { ...asset, product_ids: productId ? [productId] : [] };
  });
  for (const product of found.products) {
    product.asset_count = [...linkedTo.values()].filter((id) => id === product.id).length;
  }
  return snapshot(found);
}

export function saveBrand(token: string, input: BrandInput) {
  const found = business(token);
  found.brand = { three_words: input.three_words, colors: input.no_brand_yet ? [] : input.colors };
  return snapshot(found);
}

export function savePreferences(token: string, input: Questionnaire) {
  const found = business(token);
  found.preferences = input;
  return snapshot(found);
}

export function requestUpload(token: string, input: UploadRequest) {
  const found = business(token);
  const unsupported = new MockError(422, "unsupported_file", "Este archivo no lo podemos usar. Subí fotos.");
  if (input.kind === "video" || !PHOTO_TYPES.includes(input.content_type)) throw unsupported;
  if (input.size_bytes > MAX_PHOTO_BYTES) {
    throw new MockError(422, "unsupported_file", "Esta foto pesa más de 10 MB. Probá con otra.");
  }
  if (input.kind === "photo" && webPhotos(found).length >= 15) {
    throw new MockError(422, "too_many_photos", "Ya tenés 15 fotos.");
  }

  const id = newId("asset");
  found.assets.push({
    id,
    kind: input.kind,
    source: "web",
    status: "uploading",
    url: `/mock-api/storage/${id}`,
    thumbnail_url: null,
    width: null,
    height: null,
    duration_ms: null,
    derived_from_asset_id: null,
    owner_hint: input.owner_hint ?? null,
    palette: null,
    product_ids: [],
    reel_suitable: null,
    analyzed: false,
    archived: false,
    completedAt: null,
  });
  return { asset_id: id, upload_url: `/mock-api/storage/${id}`, upload_token: "mock", resumable: false };
}

export function completeUpload(token: string, assetId: string) {
  const asset = business(token).assets.find((item) => item.id === assetId);
  if (!asset) throw new MockError(404, "not_found", "No encontramos ese archivo.");
  if (!store.files.has(assetId)) throw new MockError(409, "upload_missing", "El archivo no terminó de subir.");
  asset.status = "ready";
  asset.completedAt = Date.now();
  if (asset.kind === "logo") asset.palette = MOCK_PALETTE;
  return toAsset(asset);
}

export function deleteAsset(token: string, assetId: string) {
  const asset = business(token).assets.find((item) => item.id === assetId);
  if (asset) asset.archived = true;
}

export function connectInstagram(token: string) {
  const found = business(token);
  found.instagram = {
    ...found.instagram,
    status: "connected",
    handle: found.business.instagram_handle ?? "tunegocio",
  };
  setTimeout(() => importInstagram(found), INSTAGRAM_IMPORT_DELAY_MS);
  return { auth_url: `/o/${encodeURIComponent(token)}?step=instagram&connected=1` };
}

export function complete(token: string): CompleteResponse {
  const found = business(token);
  const { name, category } = found.business;
  const products = found.products.filter((product) => !product.archived).length;
  const ready = activePhotos(found).filter((asset) => asset.status === "ready");
  const uploaded = ready.filter((asset) => asset.source === "web").length;
  if (!name || !category) throw new MockError(422, "missing_business", "Nos faltan los datos de tu negocio.");
  if (products < 1 || products > 5) throw new MockError(422, "missing_products", "Sumá entre 1 y 5 productos.");
  if (ready.length < 3 || uploaded > 15) throw new MockError(422, "missing_photos", "Sumá al menos 3 fotos.");
  found.completed = true;
  return { status: "generating_brand" };
}

function importInstagram(found: MockBusiness) {
  if (found.assets.some((asset) => asset.source === "instagram")) return;
  const completedAt = Date.now();
  for (const url of INSTAGRAM_PHOTOS) {
    found.assets.push({
      id: newId("asset"),
      kind: "photo",
      source: "instagram",
      status: "ready",
      url,
      thumbnail_url: null,
      width: null,
      height: null,
      duration_ms: null,
      derived_from_asset_id: null,
      owner_hint: null,
      palette: null,
      product_ids: [],
      reel_suitable: null,
      analyzed: false,
      archived: false,
      completedAt,
    });
  }
}

export function storeFile(assetId: string, file: StoredFile) {
  store.files.set(assetId, file);
}

export function readFile(assetId: string) {
  return store.files.get(assetId);
}
