/** @type {import('next').NextConfig} */
const nextConfig = {
  // `standalone` produce un servidor con solo las dependencias usadas:
  // la imagen de producción no necesita node_modules completo.
  output: 'standalone',
  reactStrictMode: true,
  poweredByHeader: false,
};

export default nextConfig;
