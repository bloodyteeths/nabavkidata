import { MetadataRoute } from 'next'
import { getAllPosts } from '@/lib/blog-posts'

const SECTOR_SLUGS = [
  'it-digitalni-uslugi', 'gradeznistvo', 'medicinska-oprema', 'kancelariski-materijali',
  'hrana-pijaloci', 'transport-vozila', 'cistenje-odrzuvanje', 'obezbeduvawe',
  'konsultantski-uslugi', 'oprema-masini', 'energetika', 'pecatenje-marketing',
]

const REGION_SLUGS = [
  'skopje', 'bitola', 'kumanovo', 'prilep', 'tetovo', 'ohrid',
  'veles', 'stip', 'strumica', 'gostivar', 'kavadarci', 'kocani',
]

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = 'https://www.nabavkidata.com'
  const currentDate = new Date()

  const blogPosts = getAllPosts()

  const blogRoutes: MetadataRoute.Sitemap = [
    {
      url: `${baseUrl}/blog`,
      lastModified: currentDate,
      changeFrequency: 'weekly',
      priority: 0.7,
    },
    ...blogPosts.map((post) => ({
      url: `${baseUrl}/blog/${post.slug}`,
      lastModified: new Date(post.date),
      changeFrequency: 'monthly' as const,
      priority: 0.6,
    })),
  ]

  const sectorRoutes: MetadataRoute.Sitemap = SECTOR_SLUGS.map(sector => ({
    url: `${baseUrl}/sectors/${sector}`,
    lastModified: currentDate,
    changeFrequency: 'weekly' as const,
    priority: 0.7,
  }))

  const sectorRegionRoutes: MetadataRoute.Sitemap = SECTOR_SLUGS.flatMap(sector =>
    REGION_SLUGS.map(region => ({
      url: `${baseUrl}/sectors/${sector}/${region}`,
      lastModified: currentDate,
      changeFrequency: 'weekly' as const,
      priority: 0.6,
    }))
  )

  return [
    {
      url: baseUrl,
      lastModified: currentDate,
      changeFrequency: 'daily',
      priority: 1.0,
    },
    {
      url: `${baseUrl}/tenders`,
      lastModified: currentDate,
      changeFrequency: 'hourly',
      priority: 0.9,
    },
    {
      url: `${baseUrl}/suppliers`,
      lastModified: currentDate,
      changeFrequency: 'daily',
      priority: 0.8,
    },
    {
      url: `${baseUrl}/awards`,
      lastModified: currentDate,
      changeFrequency: 'daily',
      priority: 0.7,
    },
    {
      url: `${baseUrl}/pricing`,
      lastModified: currentDate,
      changeFrequency: 'weekly',
      priority: 0.7,
    },
    {
      url: `${baseUrl}/privacy`,
      lastModified: currentDate,
      changeFrequency: 'monthly',
      priority: 0.5,
    },
    {
      url: `${baseUrl}/terms`,
      lastModified: currentDate,
      changeFrequency: 'monthly',
      priority: 0.5,
    },
    {
      url: `${baseUrl}/sectors`,
      lastModified: currentDate,
      changeFrequency: 'weekly',
      priority: 0.8,
    },
    ...sectorRoutes,
    ...sectorRegionRoutes,
    ...blogRoutes,
    {
      url: `${baseUrl}/alternative/esjn`,
      lastModified: currentDate,
      changeFrequency: 'monthly',
      priority: 0.7,
    },
    {
      url: `${baseUrl}/alternative/tenderwatch`,
      lastModified: currentDate,
      changeFrequency: 'monthly',
      priority: 0.7,
    },
    {
      url: `${baseUrl}/categories`,
      lastModified: currentDate,
      changeFrequency: 'weekly',
      priority: 0.8,
    },
    {
      url: `${baseUrl}/contact`,
      lastModified: currentDate,
      changeFrequency: 'monthly',
      priority: 0.5,
    },
    {
      url: `${baseUrl}/transparency`,
      lastModified: currentDate,
      changeFrequency: 'weekly',
      priority: 0.6,
    },
  ]
}
