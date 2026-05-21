import type { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: ['/dashboard', '/admin', '/settings', '/billing', '/chat', '/inbox', '/notifications', '/pipeline', '/auth', '/api', '/reactivate', '/403'],
      },
    ],
    sitemap: [
      'https://www.nabavkidata.com/sitemap.xml',
      'https://www.nabavkidata.com/tenders/sitemap.xml',
      'https://www.nabavkidata.com/suppliers/sitemap.xml',
      'https://www.nabavkidata.com/entity/sitemap.xml',
      'https://www.nabavkidata.com/awards/sitemap.xml',
    ],
    host: 'https://www.nabavkidata.com',
  };
}
