import { Metadata } from 'next';
import { api } from '@/lib/api';

type Props = {
  params: { id: string };
  children: React.ReactNode;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const supplierId = params.id;

  try {
    // Fetch supplier data for metadata
    const supplier = await api.getSupplier(supplierId);

    const title = `${supplier.company_name} - Профил на добавувач`;
    const winRate = supplier.win_rate ? (supplier.win_rate * 100).toFixed(1) : '0';
    const description = `${supplier.company_name} има вкупно ${supplier.total_bids} понуди и ${supplier.total_wins} победи (${winRate}% стапка на успех) во јавните набавки. Вкупна вредност на договори: ${new Intl.NumberFormat('mk-MK', { style: 'currency', currency: 'MKD' }).format(supplier.total_value_won_mkd || 0)}.`;

    const url = `https://www.nabavkidata.com/suppliers/${supplierId}`;

    return {
      title,
      description,
      openGraph: {
        title,
        description,
        url,
        siteName: 'Nabavkidata',
        locale: 'mk_MK',
        type: 'profile',
        images: [
          {
            url: 'https://www.nabavkidata.com/logo.png',
            width: 800,
            height: 600,
            alt: supplier.company_name,
          },
        ],
      },
      twitter: {
        card: 'summary',
        title,
        description,
      },
      alternates: {
        canonical: url,
      },
    };
  } catch (error) {
    // Fallback metadata if supplier fetch fails
    return {
      title: `Добавувач ${supplierId}`,
      description: `Профил на добавувач ${supplierId} на Nabavkidata платформата за јавни набавки во Македонија.`,
    };
  }
}

export default function SupplierLayout({ children }: Props) {
  return <>{children}</>;
}
