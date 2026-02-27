import { Metadata } from 'next';

type Props = {
  params: { id: string };
  children: React.ReactNode;
};

/** Convert dash-separated URL param to tender_id with slash: "12345-2024" → "12345/2024" */
function paramToTenderId(param: string): string {
  const match = param.match(/^(\d+)-(\d{4})$/);
  if (match) return `${match[1]}/${match[2]}`;
  return param;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  // Everything in try-catch so layout errors never crash navigation
  try {
    const tenderId = paramToTenderId(String(params.id));
    const url = `https://www.nabavkidata.com/tenders/${params.id}`;

    // Direct lightweight fetch with 3s timeout (not the full api client which
    // has retries, credentials:'include', device fingerprinting — all bad for SSR)
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);

    const response = await fetch(
      `https://api.nabavkidata.com/api/tenders/${encodeURIComponent(tenderId)}`,
      { signal: controller.signal, headers: { 'Content-Type': 'application/json' } }
    );
    clearTimeout(timeout);

    if (!response.ok) throw new Error(`API ${response.status}`);
    const tender = await response.json();

    const title = tender.title || 'Детали за тендер';
    const description = tender.description
      ? tender.description.substring(0, 160) + '...'
      : `Тендер ${tenderId} од ${tender.procuring_entity || 'државна институција'}. Проценета вредност: ${tender.estimated_value_mkd ? new Intl.NumberFormat('mk-MK', { style: 'currency', currency: 'MKD' }).format(tender.estimated_value_mkd) : 'непозната'}.`;

    return {
      title,
      description,
      openGraph: {
        title,
        description,
        url,
        siteName: 'Nabavkidata',
        locale: 'mk_MK',
        type: 'article',
        publishedTime: tender.publication_date,
        modifiedTime: tender.updated_at,
        tags: [
          tender.category,
          tender.procuring_entity,
          'јавни набавки',
          'тендери',
          'Македонија'
        ].filter((tag): tag is string => Boolean(tag)),
      },
      twitter: {
        card: 'summary_large_image',
        title,
        description,
      },
      alternates: {
        canonical: url,
      },
    };
  } catch {
    // Fallback metadata — never let this crash navigation
    const tenderId = paramToTenderId(String(params?.id || ''));
    return {
      title: `Тендер ${tenderId}`,
      description: `Детали за тендер ${tenderId} на Nabavkidata платформата за јавни набавки во Македонија.`,
    };
  }
}

export default function TenderLayout({ children }: Props) {
  return <>{children}</>;
}
