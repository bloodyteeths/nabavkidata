import type { MetadataRoute } from "next";

const API_URL = "https://api.nabavkidata.com";
const BASE_URL = "https://www.nabavkidata.com";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  try {
    const res = await fetch(
      `${API_URL}/api/seo/sitemap/awards?page=1&limit=50000`,
      { next: { revalidate: 86400 } }
    );
    if (!res.ok) return [];
    const data = await res.json();

    return (data.items || []).map(
      (t: { tender_id: string; updated_at: string | null }) => ({
        url: `${BASE_URL}/awards/${t.tender_id.replace("/", "-")}`,
        lastModified: t.updated_at ? new Date(t.updated_at) : new Date(),
        changeFrequency: "monthly" as const,
        priority: 0.6,
      })
    );
  } catch {
    return [];
  }
}
