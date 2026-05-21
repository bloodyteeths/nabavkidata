import { Metadata } from "next";
import { Suspense } from "react";
import SupplierDetailClient from "./SupplierDetailClient";

const API_URL = "https://api.nabavkidata.com";

interface SeoSupplier {
  supplier_id: string;
  company_name: string | null;
  tax_id: string | null;
  city: string | null;
  country: string | null;
  total_bids: number | null;
  total_wins: number | null;
  win_rate: number | null;
  total_value_won_mkd: number | null;
}

async function fetchSeoSupplier(supplierId: string): Promise<SeoSupplier | null> {
  try {
    const res = await fetch(`${API_URL}/api/seo/supplier/${encodeURIComponent(supplierId)}`, {
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
  const supplier = await fetchSeoSupplier(id);

  if (!supplier || !supplier.company_name) {
    return {
      title: "Добавувач | NabavkiData",
      description: "Профил на добавувач во јавни набавки.",
    };
  }

  const name = supplier.company_name;
  const descParts: string[] = [name];
  if (supplier.city) descParts.push(supplier.city);
  if (supplier.total_wins) descParts.push(`${supplier.total_wins} победи`);
  if (supplier.total_value_won_mkd) descParts.push(formatMKD(supplier.total_value_won_mkd));
  if (supplier.win_rate) descParts.push(`${Math.min(supplier.win_rate, 100).toFixed(0)}% стапка`);

  return {
    title: `${name} — профил на добавувач | NabavkiData`,
    description: descParts.join(" | "),
    openGraph: {
      title: `${name} — профил на добавувач`,
      description: descParts.join(" | "),
      url: `https://nabavkidata.com/suppliers/${encodeURIComponent(id)}`,
    },
    alternates: {
      canonical: `https://nabavkidata.com/suppliers/${encodeURIComponent(id)}`,
    },
  };
}

function JsonLd({ supplier, paramId }: { supplier: SeoSupplier; paramId: string }) {
  const jsonLd: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: supplier.company_name,
    url: `https://nabavkidata.com/suppliers/${encodeURIComponent(paramId)}`,
  };

  if (supplier.tax_id) {
    jsonLd.taxID = supplier.tax_id;
  }
  if (supplier.city) {
    jsonLd.address = {
      "@type": "PostalAddress",
      addressLocality: supplier.city,
      addressCountry: supplier.country || "MK",
    };
  }

  const breadcrumb = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Почетна", item: "https://nabavkidata.com" },
      { "@type": "ListItem", position: 2, name: "Добавувачи", item: "https://nabavkidata.com/suppliers" },
      { "@type": "ListItem", position: 3, name: supplier.company_name || "Добавувач" },
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

export default async function SupplierPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supplier = await fetchSeoSupplier(id);

  return (
    <>
      {supplier && <JsonLd supplier={supplier} paramId={id} />}

      {supplier && (
        <div className="sr-only" aria-hidden="true">
          <h1>{supplier.company_name}</h1>
          {supplier.tax_id && <p>ЕДБ: {supplier.tax_id}</p>}
          {supplier.city && <p>Град: {supplier.city}</p>}
          {supplier.total_wins != null && <p>Победи: {supplier.total_wins}</p>}
          {supplier.total_bids != null && <p>Понуди: {supplier.total_bids}</p>}
          {supplier.total_value_won_mkd != null && <p>Вредност: {formatMKD(supplier.total_value_won_mkd)}</p>}
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
        <SupplierDetailClient />
      </Suspense>
    </>
  );
}
