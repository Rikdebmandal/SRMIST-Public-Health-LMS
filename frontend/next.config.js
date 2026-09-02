/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: { remotePatterns: [{ protocol: 'http', hostname: 'localhost' }] },
  async rewrites() {
    return [
      {
        source: '/media/:path*',
        destination: (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/media/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
