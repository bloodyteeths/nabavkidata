import type { MetadataRoute } from "next";

const API_URL = "https://api.nabavkidata.com";
const BASE_URL = "https://www.nabavkidata.com";
const CHUNK_SIZE = 50000;

export async function generateSitemaps() {
  try {
    const res = await fetch(`${API_URL}/api/seo/sitemap/suppliers/count`, {
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
      `${API_URL}/api/seo/sitemap/suppliers?page=${page}&limit=${CHUNK_SIZE}`,
      { next: { revalidate: 86400 } }
    );
    if (!res.ok) return [];
    const data = await res.json();

    return (data.items || []).map(
      (s: { supplier_id: string; company_name: string }) => ({
        url: `${BASE_URL}/suppliers/${encodeURIComponent(s.supplier_id)}`,
        lastModified: new Date(),
        changeFrequency: "weekly" as const,
        priority: 0.6,
      })
    );
  } catch {
    return [];
  }
}
