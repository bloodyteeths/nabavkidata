import { Metadata } from 'next';
import { api } from '@/lib/api';

type Props = {
  params: { id: string[] };
  children: React.ReactNode;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  // [...id] catch-all: params.id is string[] (e.g. ["12345", "2024"])
  const tenderId = params.id.join('/');

  try {
    // Fetch tender data for metadata
    const tender = await api.getTender(tenderId);

    const title = tender.title || 'Детали за тендер';
    const description = tender.description
      ? tender.description.substring(0, 160) + '...'
      : `Тендер ${tenderId} од ${tender.procuring_entity || 'државна институција'}. Проценета вредност: ${tender.estimated_value_mkd ? new Intl.NumberFormat('mk-MK', { style: 'currency', currency: 'MKD' }).format(tender.estimated_value_mkd) : 'непозната'}.`;

    const url = `https://www.nabavkidata.com/tenders/${tenderId}`;

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
  } catch (error) {
    // Fallback metadata if tender fetch fails
    return {
      title: `Тендер ${tenderId}`,
      description: `Детали за тендер ${tenderId} на Nabavkidata платформата за јавни набавки во Македонија.`,
    };
  }
}

export default function TenderLayout({ children }: Props) {
  return <>{children}</>;
}
