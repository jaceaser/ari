import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  devIndicators: false,
  cacheComponents: true,
  images: {
    remotePatterns: [
      {
        hostname: "avatar.vercel.sh",
      },
    ],
  },
  async headers() {
    const isDev = process.env.NODE_ENV === "development";
    const frameAncestors = isDev
      ? "'self' http://localhost:* https://reilabs.ai https://www.reilabs.ai"
      : "'self' https://reilabs.ai https://www.reilabs.ai";

    return [
      {
        // Only the /try embed page can be iframed from reilabs.ai
        source: "/try",
        headers: [
          {
            key: "Content-Security-Policy",
            value: `frame-ancestors ${frameAncestors}`,
          },
        ],
      },
    ];
  },
};

export default nextConfig;
