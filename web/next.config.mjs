/** @type {import('next').NextConfig} */
const apiUrl = (process.env.API_URL || "http://127.0.0.1:8080").replace(/\/$/, "");

const nextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
