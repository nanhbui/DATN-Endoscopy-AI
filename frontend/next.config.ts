import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces a self-contained bundle for Docker: node server.js
  output: 'standalone',

  // Proxy /api/* to FastAPI backend (development only; Docker uses direct fetch)
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8001'}/:path*`,
      },
    ];
  },
};

export default nextConfig;
