/** @type {import('next').NextConfig} */
const apiInternal =
  process.env.API_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:4000";

const nextConfig = {
  output: "standalone",
  async rewrites() {
    const base = apiInternal.replace(/\/$/, "");
    return [
      { source: "/api/v1/:path*", destination: `${base}/api/v1/:path*` },
      { source: "/api/config", destination: `${base}/api/config` },
      { source: "/api/config/:path*", destination: `${base}/api/config/:path*` },
    ];
  },
};

export default nextConfig;
