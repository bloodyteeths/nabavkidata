'use client';

import { useState } from 'react';
import { Search, TrendingUp } from 'lucide-react';
import { api, EPazarItemAggregation } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { formatCurrency } from '@/lib/utils';

export function PriceCheck() {
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<EPazarItemAggregation[]>([]);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!search.trim()) return;

    setLoading(true);
    setError(null);
    setSearched(true);

    try {
      const data = await api.getEPazarItemsAggregations(search);
      setResults(data.aggregations || []);
    } catch (err) {
      console.error('Price check failed:', err);
      setError('Не успеавме да ги вчитаме цените');
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-green-600" />
          Провери цена
        </CardTitle>
        <CardDescription>
          Внесете производ за да видите пазарни цени од претходни тендери
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              type="text"
              placeholder="пр. хартија А4, тонер, гориво..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10"
            />
          </div>
          <Button type="submit" disabled={loading || !search.trim()}>
            {loading ? 'Барам...' : 'Провери'}
          </Button>
        </form>

        {error && (
          <p className="text-red-600 text-sm">{error}</p>
        )}

        {searched && !loading && results.length === 0 && !error && (
          <p className="text-gray-500 text-center py-4">
            Нема резултати за "{search}"
          </p>
        )}

        {results.length > 0 && (
          <div className="space-y-3">
            {results.slice(0, 5).map((item, idx) => (
              <div key={idx} className="p-3 bg-gray-50 rounded-lg">
                <div className="font-medium">{item.item_name}</div>
                {item.unit && (
                  <div className="text-xs text-gray-500 mb-2">Единица: {item.unit}</div>
                )}
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <span className="text-gray-500">Мин:</span>
                    <span className="ml-1 font-medium text-green-600">
                      {formatCurrency(item.min_unit_price)}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Просек:</span>
                    <span className="ml-1 font-medium">
                      {formatCurrency(item.avg_unit_price)}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Макс:</span>
                    <span className="ml-1 font-medium text-red-600">
                      {formatCurrency(item.max_unit_price)}
                    </span>
                  </div>
                </div>
                <div className="text-xs text-gray-400 mt-1">
                  Базирано на {item.tender_count} тендери
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
