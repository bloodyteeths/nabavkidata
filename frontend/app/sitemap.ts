import { MetadataRoute } from 'next'
import { getAllPosts } from '@/lib/blog-posts'

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
    ...blogRoutes,
    // Note: Dynamic tender and supplier pages can be added here in the future
    // by fetching data from the API and mapping each tender/supplier to a URL
    // Example:
    // ...tenders.map((tender) => ({
    //   url: `${baseUrl}/tenders/${encodeURIComponent(tender.tender_id)}`,
    //   lastModified: tender.updated_at || currentDate,
    //   changeFrequency: 'weekly' as const,
    //   priority: 0.6,
    // })),
  ]
}
