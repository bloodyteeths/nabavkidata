/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: false,
  },
  experimental: {
    missingSuspenseWithCSRBailout: false,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'https://api.nabavkidata.com/api/:path*',
      },
    ]
  },
}

module.exports = nextConfig
// Build trigger: 1764115009
