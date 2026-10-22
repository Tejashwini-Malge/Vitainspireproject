/** @type {import('next').NextConfig} */
const apiOrigin = process.env.VITA_API_URL ?? "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  // Same-origin API: the browser calls /api/* and Next forwards to the FastAPI backend.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/:path*` }];
  },
};

export default nextConfig;
