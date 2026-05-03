import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // reactStrictMode disabled: StrictMode double-invokes effects in dev,
  // which creates two ReadableStream readers on the SSE body (second read fails
  // with "body already consumed") — breaks streaming.
  reactStrictMode: false,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**" },
    ],
  },
};

export default nextConfig;
