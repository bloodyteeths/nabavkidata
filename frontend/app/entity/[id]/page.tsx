import { Metadata } from "next";
import EntityDetailClient from "./EntityDetailClient";

const API_URL = "https://api.nabavkidata.com";

interface SeoEntity {
  entity_id: string;
  entity_name: string;
  entity_type: string | null;
  category: string | null;
  city: string | null;
  total_tenders: number;
  total_value_mkd: number | null;
}

async function fetchSeoEntity(entityId: string): Promise<SeoEntity | null> {
  try {
    const res = await fetch(`${API_URL}/api/seo/entity/${encodeURIComponent(entityId)}`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

function formatMKD(value: number | null | undefined): string {
  if (!value) return "";
  return Math.trunc(value).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",") + " ден";
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const entity = await fetchSeoEntity(id);

  if (!entity) {
    return {
      title: "Договорен орган | NabavkiData",
      description: "Профил на институција во јавни набавки.",
    };
  }

  const name = entity.entity_name;
  const descParts: string[] = [name];
  if (entity.city) descParts.push(entity.city);
  if (entity.total_tenders) descParts.push(`${entity.total_tenders} тендери`);
  if (entity.total_value_mkd) descParts.push(formatMKD(entity.total_value_mkd));

  return {
    title: `${name} — тендери и набавки | NabavkiData`,
    description: descParts.join(" | "),
    openGraph: {
      title: `${name} — договорен орган`,
      description: descParts.join(" | "),
      url: `https://nabavkidata.com/entity/${encodeURIComponent(id)}`,
    },
    alternates: {
      canonical: `https://nabavkidata.com/entity/${encodeURIComponent(id)}`,
    },
  };
}

function JsonLd({ entity, paramId }: { entity: SeoEntity; paramId: string }) {
  const jsonLd: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "GovernmentOrganization",
    name: entity.entity_name,
    url: `https://nabavkidata.com/entity/${encodeURIComponent(paramId)}`,
    areaServed: { "@type": "Country", name: "North Macedonia" },
  };

  if (entity.city) {
    jsonLd.address = {
      "@type": "PostalAddress",
      addressLocality: entity.city,
      addressCountry: "MK",
    };
  }

  const breadcrumb = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Почетна", item: "https://nabavkidata.com" },
      { "@type": "ListItem", position: 2, name: "Институции", item: "https://nabavkidata.com/entity" },
      { "@type": "ListItem", position: 3, name: entity.entity_name },
    ],
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumb) }}
      />
    </>
  );
}

export default async function EntityPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const entity = await fetchSeoEntity(id);

  return (
    <>
      {entity && <JsonLd entity={entity} paramId={id} />}

      {entity && (
        <div className="sr-only" aria-hidden="true">
          <h1>{entity.entity_name}</h1>
          {entity.entity_type && <p>Тип: {entity.entity_type}</p>}
          {entity.city && <p>Град: {entity.city}</p>}
          <p>Вкупно тендери: {entity.total_tenders}</p>
          {entity.total_value_mkd && <p>Вкупна вредност: {formatMKD(entity.total_value_mkd)}</p>}
        </div>
      )}

      <EntityDetailClient />
    </>
  );
}
