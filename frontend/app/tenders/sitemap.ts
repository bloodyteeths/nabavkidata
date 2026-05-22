import type { MetadataRoute } from "next";

const API_URL = "https://api.nabavkidata.com";
const BASE_URL = "https://www.nabavkidata.com";
const CHUNK_SIZE = 50000;

export async function generateSitemaps() {
  try {
    const res = await fetch(`${API_URL}/api/seo/sitemap/tenders/count`, {
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
      `${API_URL}/api/seo/sitemap/tenders?page=${page}&limit=${CHUNK_SIZE}`,
      { next: { revalidate: 86400 } }
    );
    if (!res.ok) return [];
    const data = await res.json();

    return (data.items || []).map(
      (t: { tender_id: string; updated_at: string | null; status: string }) => ({
        url: `${BASE_URL}/tenders/${t.tender_id.replace("/", "-")}`,
        lastModified: t.updated_at ? new Date(t.updated_at) : new Date(),
        changeFrequency:
          t.status === "open" ? ("daily" as const) : ("monthly" as const),
        priority: t.status === "open" ? 0.8 : 0.5,
      })
    );
  } catch {
    return [];
  }
}
