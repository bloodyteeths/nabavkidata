import { Metadata } from "next";
import { Suspense } from "react";
import TenderDetailClient from "./TenderDetailClient";

const API_URL = "https://api.nabavkidata.com";

function tenderIdFromParam(param: string): string {
  const match = param.match(/^(\d+)-(\d{4})$/);
  if (match) return `${match[1]}/${match[2]}`;
  return param;
}

function formatMKD(value: number | null | undefined): string {
  if (!value) return "";
  return Math.trunc(value).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",") + " ден";
}

interface SeoTender {
  tender_id: string;
  title: string | null;
  description: string | null;
  procuring_entity: string | null;
  estimated_value_mkd: number | null;
  actual_value_mkd: number | null;
  status: string | null;
  closing_date: string | null;
  publication_date: string | null;
  opening_date: string | null;
  cpv_code: string | null;
  winner: string | null;
  procedure_type: string | null;
  category: string | null;
}

async function fetchSeoTender(tenderId: string): Promise<SeoTender | null> {
  try {
    const res = await fetch(`${API_URL}/api/seo/tender/${encodeURIComponent(tenderId)}`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const tenderId = tenderIdFromParam(id);
  const tender = await fetchSeoTender(tenderId);

  if (!tender) {
    return {
      title: `Тендер ${tenderId} | NabavkiData`,
      description: "Детали за јавна набавка на NabavkiData.",
    };
  }

  const title = tender.title
    ? `${tender.title.slice(0, 70)} | NabavkiData`
    : `Тендер ${tenderId} | NabavkiData`;

  const descParts: string[] = [];
  if (tender.procuring_entity) descParts.push(tender.procuring_entity);
  if (tender.estimated_value_mkd) descParts.push(formatMKD(tender.estimated_value_mkd));
  if (tender.status === "awarded" && tender.winner) descParts.push(`Победник: ${tender.winner}`);
  if (tender.closing_date) descParts.push(`Рок: ${tender.closing_date}`);
  const description = descParts.length > 0
    ? descParts.join(" | ")
    : tender.description?.slice(0, 160) || "Детали за јавна набавка.";

  return {
    title,
    description,
    openGraph: {
      title: tender.title || `Тендер ${tenderId}`,
      description,
      url: `https://nabavkidata.com/tenders/${id}`,
      type: "article",
    },
    alternates: {
      canonical: `https://nabavkidata.com/tenders/${id}`,
    },
  };
}

function statusLabel(status: string | null): string {
  switch (status) {
    case "open": return "Отворен";
    case "awarded": return "Доделен";
    case "cancelled": return "Поништен";
    default: return status || "Непознат";
  }
}

function JsonLd({ tender, paramId }: { tender: SeoTender; paramId: string }) {
  const jsonLd: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "GovernmentService",
    name: tender.title || `Тендер ${tender.tender_id}`,
    description: tender.description?.slice(0, 500) || undefined,
    provider: tender.procuring_entity
      ? { "@type": "GovernmentOrganization", name: tender.procuring_entity }
      : undefined,
    url: `https://nabavkidata.com/tenders/${paramId}`,
    areaServed: { "@type": "Country", name: "North Macedonia" },
  };

  if (tender.publication_date) {
    jsonLd.datePublished = tender.publication_date;
  }
  if (tender.closing_date) {
    jsonLd.expires = tender.closing_date;
  }

  const offers: Record<string, unknown> = { "@type": "Offer" };
  if (tender.estimated_value_mkd) {
    offers.price = tender.estimated_value_mkd;
    offers.priceCurrency = "MKD";
  }
  if (tender.status === "awarded" && tender.actual_value_mkd) {
    offers.price = tender.actual_value_mkd;
    offers.priceCurrency = "MKD";
  }
  if (offers.price) {
    jsonLd.offers = offers;
  }

  const breadcrumb = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Почетна", item: "https://nabavkidata.com" },
      { "@type": "ListItem", position: 2, name: "Тендери", item: "https://nabavkidata.com/tenders" },
      { "@type": "ListItem", position: 3, name: tender.title || tender.tender_id },
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

export default async function TenderPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const tenderId = tenderIdFromParam(id);
  const tender = await fetchSeoTender(tenderId);

  return (
    <>
      {tender && <JsonLd tender={tender} paramId={id} />}

      {/* SSR-visible content for crawlers */}
      {tender && (
        <div className="sr-only" aria-hidden="true">
          <h1>{tender.title || `Тендер ${tender.tender_id}`}</h1>
          {tender.procuring_entity && <p>Договорен орган: {tender.procuring_entity}</p>}
          {tender.estimated_value_mkd && <p>Проценета вредност: {formatMKD(tender.estimated_value_mkd)}</p>}
          {tender.winner && <p>Победник: {tender.winner}</p>}
          {tender.status && <p>Статус: {statusLabel(tender.status)}</p>}
          {tender.closing_date && <p>Рок: {tender.closing_date}</p>}
          {tender.cpv_code && <p>CPV: {tender.cpv_code}</p>}
          {tender.description && <p>{tender.description.slice(0, 500)}</p>}
          <nav>
            {tender.procuring_entity && (
              <a href={`/entity/${encodeURIComponent(tender.procuring_entity)}`}>Тендери од {tender.procuring_entity}</a>
            )}
            {tender.winner && (
              <a href={`/suppliers?search=${encodeURIComponent(tender.winner)}`}>Профил на {tender.winner}</a>
            )}
            {tender.cpv_code && (
              <a href={`/categories/${tender.cpv_code}`}>Сите тендери со CPV {tender.cpv_code}</a>
            )}
          </nav>
        </div>
      )}

      <Suspense fallback={
        <div className="container mx-auto py-8 px-4">
          <div className="flex items-center justify-center h-64">
            <div className="flex items-center gap-2">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
              <span>Се вчитува...</span>
            </div>
          </div>
        </div>
      }>
        <TenderDetailClient />
      </Suspense>
    </>
  );
}
