/** @type {import('next').NextConfig} */
const nextConfig = {
  // Proxy API calls to FastAPI so the browser stays same-origin (avoids CORS / Network Error).
  async rewrites() {
    const backend = process.env.BACKEND_URL || "http://127.0.0.1:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`,
      },
    ];
  },
  images: {
    remotePatterns: [
      { protocol: "http", hostname: "localhost", port: "8000" },
      { protocol: "http", hostname: "127.0.0.1", port: "8000" },
      { protocol: "http", hostname: "localhost", port: "3000" },
      { protocol: "http", hostname: "127.0.0.1", port: "3000" },
    ],
  },
};

module.exports = nextConfig;
