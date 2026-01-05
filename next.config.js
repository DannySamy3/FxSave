/**
 * Next.js Configuration
 *
 * Configuration for the Gold Price Prediction frontend
 * Minimal setup for fast development and production builds
 */

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable React strict mode for development
  reactStrictMode: true,

  // Image optimization settings
  images: {
    unoptimized: true,
  },

  // API routes and staticProps caching
  swcMinify: true,

  // Environment variables
  env: {
    NEXT_PUBLIC_APP_NAME: "Gold Price Prediction",
  },

  // Headers for static content
  async headers() {
    return [
      {
        source: "/api/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=300, stale-while-revalidate=600",
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
