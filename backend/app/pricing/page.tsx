import ItemPriceSearch from '@/components/pricing/ItemPriceSearch';

export const metadata = {
  title: 'Истражување на цени по артикл | Nabavkidata',
  description: 'Пребарувајте цени на специфични производи и услуги низ сите тендери',
};

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <ItemPriceSearch />
    </div>
  );
}
