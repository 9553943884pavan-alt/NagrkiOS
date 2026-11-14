// Evaluated by Vercel at deployment time; no backend secret enters the bundle.
const value = process.env.NAGRIKOS_RENDER_ORIGIN;
if (!value) throw new Error('Set NAGRIKOS_RENDER_ORIGIN to the Render HTTPS origin');
const origin = new URL(value);
if (origin.protocol !== 'https:' || origin.origin !== value ||
    !origin.hostname || origin.hostname === 'localhost' ||
    origin.hostname === '127.0.0.1' || origin.username || origin.password) {
  throw new Error('NAGRIKOS_RENDER_ORIGIN must be a bare HTTPS origin');
}
if (process.env.VITE_API_BASE) {
  throw new Error('Do not set VITE_API_BASE; the frontend uses its same-origin /api proxy');
}

export const config = {
  rewrites: [
    { source: '/api/:path*', destination: `${origin.origin}/api/:path*` },
    { source: '/(.*)', destination: '/index.html' },
  ],
  headers: [{
    source: '/api/:path*',
    headers: [{ key: 'x-vercel-enable-rewrite-caching', value: '0' }],
  }],
};
