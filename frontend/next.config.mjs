/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Static export keeps the PWA hostable anywhere (Vercel, GitHub Pages, plain CDN).
  // Demo mode needs no server; REST mode just needs NEXT_PUBLIC_API_URL.
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  // Service worker + demo data live in public/ and are copied verbatim.
};

export default nextConfig;
