import { Metadata } from "next";
import { Suspense } from "react";
import AwardDetailClient from "./AwardDetailClient";

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

interface SeoAward {
  tender_id: string;
  title: string | null;
  description: string | null;
  procuring_entity: string | null;
  estimated_value_mkd: number | null;
  actual_value_mkd: number | null;
  winner: string | null;
  num_bidders: number | null;
  publication_date: string | null;
  closing_date: string | null;
  cpv_code: string | null;
  procedure_type: string | null;
  category: string | null;
}

async function fetchSeoAward(tenderId: string): Promise<SeoAward | null> {
  try {
    const res = await fetch(`${API_URL}/api/seo/award/${encodeURIComponent(tenderId)}`, {
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
  const award = await fetchSeoAward(tenderId);

  if (!award) {
    return {
      title: `Доделена набавка ${tenderId} | NabavkiData`,
      description: "Детали за доделена јавна набавка на NabavkiData.",
    };
  }

  const title = award.winner && award.title
    ? `${award.winner} ја доби набавката: ${award.title}`.slice(0, 70) + " | NabavkiData"
    : `Доделена набавка ${tenderId} | NabavkiData`;

  const descParts: string[] = [];
  if (award.winner) descParts.push(`Победник: ${award.winner}`);
  if (award.procuring_entity) descParts.push(award.procuring_entity);
  if (award.actual_value_mkd) descParts.push(formatMKD(award.actual_value_mkd));
  else if (award.estimated_value_mkd) descParts.push(formatMKD(award.estimated_value_mkd));
  if (award.num_bidders) descParts.push(`${award.num_bidders} понудувачи`);
  const description = descParts.length > 0
    ? descParts.join(" | ")
    : award.description?.slice(0, 160) || "Детали за доделена јавна набавка.";

  return {
    title,
    description,
    openGraph: {
      title: award.winner
        ? `${award.winner} ја доби набавката: ${award.title || tenderId}`
        : `Доделена набавка ${tenderId}`,
      description,
      url: `https://nabavkidata.com/awards/${id}`,
      type: "article",
    },
    alternates: {
      canonical: `https://nabavkidata.com/awards/${id}`,
    },
  };
}

function JsonLd({ award, paramId }: { award: SeoAward; paramId: string }) {
  const headline = award.winner
    ? `${award.winner} ја доби набавката: ${award.title || "Јавна набавка"}`
    : award.title || `Доделена набавка ${award.tender_id}`;

  const descParts: string[] = [];
  if (award.procuring_entity) descParts.push(`Договорен орган: ${award.procuring_entity}`);
  if (award.actual_value_mkd) descParts.push(`Вредност: ${formatMKD(award.actual_value_mkd)}`);
  else if (award.estimated_value_mkd) descParts.push(`Проценета вредност: ${formatMKD(award.estimated_value_mkd)}`);
  if (award.num_bidders) descParts.push(`Број на понудувачи: ${award.num_bidders}`);

  const jsonLd: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: headline.slice(0, 110),
    description: descParts.join(". ") || award.description?.slice(0, 500) || undefined,
    datePublished: award.publication_date || undefined,
    publisher: {
      "@type": "Organization",
      name: "NabavkiData",
    },
    url: `https://nabavkidata.com/awards/${paramId}`,
    about: {
      "@type": "GovernmentService",
      name: award.title || `Набавка ${award.tender_id}`,
      provider: award.procuring_entity
        ? { "@type": "GovernmentOrganization", name: award.procuring_entity }
        : undefined,
    },
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}

export default async function AwardPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const tenderId = tenderIdFromParam(id);
  const award = await fetchSeoAward(tenderId);

  return (
    <>
      {award && <JsonLd award={award} paramId={id} />}

      {/* SSR-visible content for crawlers */}
      {award && (
        <div className="sr-only" aria-hidden="true">
          <h1>{award.winner} ја доби набавката: {award.title || `Набавка ${award.tender_id}`}</h1>
          {award.procuring_entity && <p>Договорен орган: {award.procuring_entity}</p>}
          {award.actual_value_mkd && <p>Договорена вредност: {formatMKD(award.actual_value_mkd)}</p>}
          {award.estimated_value_mkd && <p>Проценета вредност: {formatMKD(award.estimated_value_mkd)}</p>}
          {award.winner && <p>Победник: {award.winner}</p>}
          {award.num_bidders && <p>Број на понудувачи: {award.num_bidders}</p>}
          {award.publication_date && <p>Датум на објава: {award.publication_date}</p>}
          {award.cpv_code && <p>CPV: {award.cpv_code}</p>}
          {award.procedure_type && <p>Постапка: {award.procedure_type}</p>}
          {award.description && <p>{award.description.slice(0, 500)}</p>}
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
        <AwardDetailClient />
      </Suspense>
    </>
  );
}
