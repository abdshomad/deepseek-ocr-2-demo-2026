import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  basePath: "/next",
  async rewrites() {
    return [
      {
        source: "/v2/:path*",
        destination: "http://127.0.0.1:7873/v2/:path*",
      },
    ];
  },
};

export default nextConfig;


