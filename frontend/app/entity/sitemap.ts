import type { MetadataRoute } from "next";

const API_URL = "https://api.nabavkidata.com";
const BASE_URL = "https://www.nabavkidata.com";

export async function generateSitemaps() {
  try {
    const res = await fetch(`${API_URL}/api/seo/sitemap/entities/count`, {
      next: { revalidate: 86400 },
    });
    if (!res.ok) return [{ id: 0 }];
    const data = await res.json();
    return Array.from({ length: data.pages || 1 }, (_, i) => ({ id: i }));
  } catch {
    return [{ id: 0 }];
  }
}

export default async function sitemap({
  id,
}: {
  id: number;
}): Promise<MetadataRoute.Sitemap> {
  const page = id + 1;
  try {
    const res = await fetch(
      `${API_URL}/api/seo/sitemap/entities?page=${page}&limit=50000`,
      { next: { revalidate: 86400 } }
    );
    if (!res.ok) return [];
    const data = await res.json();

    return (data.items || []).map(
      (e: { entity_id: string; entity_name: string }) => ({
        url: `${BASE_URL}/entity/${encodeURIComponent(e.entity_id)}`,
        lastModified: new Date(),
        changeFrequency: "weekly" as const,
        priority: 0.7,
      })
    );
  } catch {
    return [];
  }
}
