import type { NextConfig } from "next";

// Local yarn/Docker only. On Vercel, vercel.json routes /api/v1 to the api
// service before this rewrite runs. A service binding is not available here:
// rewrites are fixed at build time, and bindings are injected into functions.
const apiUrl = (process.env.API_URL || "http://localhost:8000").replace(
  /\/$/,
  "",
);

const nextConfig: NextConfig = {
  output: "standalone",
  cacheComponents: true,
  partialPrefetching: true,
  // Keep demo corpus inside the standalone/Vercel web bundle (policies + directory).
  outputFileTracingIncludes: {
    "/*": ["./data/**/*"],
  },
  turbopack: {
    root: __dirname,
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return {
      beforeFiles: [
        {
          source: "/api/v1/:path*",
          destination: `${apiUrl}/api/v1/:path*`,
        },
      ],
    };
  },
};

export default nextConfig;
