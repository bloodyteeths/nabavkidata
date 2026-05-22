import type { MetadataRoute } from "next";

const API_URL = "https://api.nabavkidata.com";
const BASE_URL = "https://www.nabavkidata.com";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  try {
    const res = await fetch(`${API_URL}/api/seo/sitemap/cpv`, {
      next: { revalidate: 86400 },
    });
    if (!res.ok) return [];
    const data = await res.json();

    return (data.items || []).map(
      (c: { cpv_code: string }) => ({
        url: `${BASE_URL}/categories/${c.cpv_code}`,
        lastModified: new Date(),
        changeFrequency: "weekly" as const,
        priority: 0.7,
      })
    );
  } catch {
    return [];
  }
}
