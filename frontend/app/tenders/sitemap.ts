import type { MetadataRoute } from "next";

const API_URL = "https://api.nabavkidata.com";
const BASE_URL = "https://www.nabavkidata.com";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  try {
    const res = await fetch(
      `${API_URL}/api/seo/sitemap/tenders?page=1&limit=50000`,
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
