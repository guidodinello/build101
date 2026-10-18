import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  serverExternalPackages: ["@takumi-rs/core"],
  outputFileTracingIncludes: {
    "/api/render": ["./lib/post-render/fonts/**"],
    "/api/render/preview": ["./lib/post-render/fonts/**", "./components/landing/photos/**"],
  },
  partialPrefetching: true,
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
