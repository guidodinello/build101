import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";
const onVercel = Boolean(process.env.VERCEL);
const isPreview = process.env.VERCEL_ENV === "preview";

// The origin of an env URL for the CSP. On Vercel a missing or invalid value fails the build:
// shipping without it would either break the wizard or force a wildcard source, so the local
// `fallback` is never used there. Locally an unset value is skipped, since the mock API serves
// everything from 'self'.
function originOf(name: string, fallback?: string): string | null {
  const value = process.env[name] ?? (onVercel ? undefined : fallback);
  if (!value) {
    if (onVercel) throw new Error(`${name} must be set to build the Content-Security-Policy`);
    return null;
  }
  try {
    return new URL(value).origin;
  } catch {
    throw new Error(`${name} is not a valid URL`);
  }
}

const apiOrigin = originOf("NEXT_PUBLIC_API_URL", "http://localhost:8000");
// Signed upload URLs (XHR PUT) and signed image URLs both live on the Supabase Storage origin.
const storageOrigin = originOf("SUPABASE_URL");

// The Vercel Toolbar injected on preview deployments, per
// https://vercel.com/docs/vercel-toolbar/managing-toolbar#using-a-content-security-policy
const toolbar = {
  script: ["https://vercel.live"],
  connect: ["https://vercel.live", "wss://ws-us3.pusher.com"],
  img: ["https://vercel.live", "https://vercel.com"],
  frame: ["https://vercel.live"],
  style: ["https://vercel.live"],
  font: ["https://vercel.live", "https://assets.vercel.com"],
};

function sources(...lists: (string | null | readonly string[] | false)[]) {
  return lists.flat().filter(Boolean).join(" ");
}

// Inline scripts stay allowed: a nonce CSP forces dynamic rendering and rules out
// `cacheComponents` / partial prefetching (Next.js CSP guide), so this policy does not stop
// inline-script injection. It does lock framing, plugins, <base>, forms and where the page can
// load images from or send data to.
const csp = [
  "default-src 'self'",
  `script-src ${sources("'self'", "'unsafe-inline'", isDev && "'unsafe-eval'", isPreview && toolbar.script)}`,
  `style-src ${sources("'self'", "'unsafe-inline'", isPreview && toolbar.style)}`,
  `img-src ${sources("'self'", "blob:", "data:", storageOrigin, isPreview && toolbar.img)}`,
  `font-src ${sources("'self'", isPreview && toolbar.font)}`,
  `connect-src ${sources("'self'", apiOrigin, storageOrigin, isDev && "ws:", isPreview && toolbar.connect)}`,
  isPreview && `frame-src ${toolbar.frame.join(" ")}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  onVercel && "upgrade-insecure-requests",
]
  .filter(Boolean)
  .join("; ");

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  serverExternalPackages: ["@takumi-rs/core"],
  outputFileTracingIncludes: {
    "/api/render": ["./lib/post-render/fonts/**"],
    "/api/render/preview": ["./lib/post-render/fonts/**", "./components/landing/photos/**"],
  },
  partialPrefetching: true,
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
        ],
      },
      // The onboarding token is in the path: keep it out of Referer on API and storage requests.
      { source: "/o/:path*", headers: [{ key: "Referrer-Policy", value: "no-referrer" }] },
      // The mock API stores whatever content type a client declares (dev only). Headers set in a
      // route handler lose to the rule above, so the sandbox lives here, after it, and wins.
      { source: "/mock-api/storage/:path*", headers: [{ key: "Content-Security-Policy", value: "sandbox" }] },
    ];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
