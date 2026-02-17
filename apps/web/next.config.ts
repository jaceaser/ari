import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  devIndicators: false,
  cacheComponents: true,
  images: {
    remotePatterns: [],
  },
};

export default nextConfig;
