import type { MetadataRoute } from 'next';

const BASE = 'https://www.nabavkidata.com';
const TENDER_SITEMAP_CHUNKS = 6;

export default function robots(): MetadataRoute.Robots {
  const tenderSitemaps = Array.from(
    { length: TENDER_SITEMAP_CHUNKS },
    (_, i) => `${BASE}/tenders/sitemap/${i}.xml`
  );

  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: ['/dashboard', '/admin', '/settings', '/billing', '/chat', '/inbox', '/notifications', '/pipeline', '/auth', '/api', '/reactivate', '/403'],
      },
    ],
    sitemap: [
      `${BASE}/sitemap.xml`,
      ...tenderSitemaps,
      `${BASE}/suppliers/sitemap.xml`,
      `${BASE}/entity/sitemap.xml`,
      `${BASE}/awards/sitemap.xml`,
      `${BASE}/categories/sitemap.xml`,
    ],
    host: BASE,
  };
}
