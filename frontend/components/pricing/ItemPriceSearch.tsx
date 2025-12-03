'use client';

import { useState, useCallback } from 'react';
import { api } from '@/lib/api';
import debounce from 'lodash/debounce';

interface ItemPriceResult {
  item_name: string;
  unit_price?: number;
  total_price?: number;
  quantity?: number;
  unit?: string;
  tender_id: string;
  tender_title: string;
  date?: string;
  source: 'epazar' | 'nabavki' | 'document';
}

interface ItemPriceSearchResponse {
  query: string;
  results: ItemPriceResult[];
  statistics: {
    count: number;
    min_price?: number;
    max_price?: number;
    avg_price?: number;
    median_price?: number;
  };
}

type SortField = 'item_name' | 'unit_price' | 'date' | 'tender_title';
type SortOrder = 'asc' | 'desc';

export default function ItemPriceSearch() {
  const [query, setQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [results, setResults] = useState<ItemPriceResult[]>([]);
  const [statistics, setStatistics] = useState<ItemPriceSearchResponse['statistics'] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>('date');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  const searchItems = async (searchQuery: string) => {
    if (!searchQuery || searchQuery.length < 3) {
      setResults([]);
      setStatistics(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await api.searchItemPrices(searchQuery, 50);
      setQuery(response.query);
      setResults(response.results);
      setStatistics(response.statistics);
    } catch (err: any) {
      setError(err.message || 'Failed to search item prices');
      setResults([]);
      setStatistics(null);
    } finally {
      setLoading(false);
    }
  };

  // Debounced search function
  const debouncedSearch = useCallback(
    debounce((searchQuery: string) => {
      searchItems(searchQuery);
    }, 500),
    []
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchInput(value);
    debouncedSearch(value);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    searchItems(searchInput);
  };

  const sortResults = (field: SortField) => {
    const newOrder = sortField === field && sortOrder === 'asc' ? 'desc' : 'asc';
    setSortField(field);
    setSortOrder(newOrder);

    const sorted = [...results].sort((a, b) => {
      let aVal: any = a[field];
      let bVal: any = b[field];

      if (field === 'date') {
        aVal = a.date ? new Date(a.date).getTime() : 0;
        bVal = b.date ? new Date(b.date).getTime() : 0;
      }

      if (field === 'unit_price') {
        aVal = a.unit_price || 0;
        bVal = b.unit_price || 0;
      }

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return newOrder === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      return newOrder === 'asc' ? aVal - bVal : bVal - aVal;
    });

    setResults(sorted);
  };

  const formatPrice = (price?: number) => {
    if (!price) return '-';
    return new Intl.NumberFormat('mk-MK', {
      style: 'decimal',
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(price) + ' МКД';
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return new Intl.DateTimeFormat('mk-MK', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(date);
  };

  const getSourceBadge = (source: string) => {
    const badges = {
      epazar: { label: 'e-Пазар', color: 'bg-blue-100 text-blue-800' },
      nabavki: { label: 'е-Набавки', color: 'bg-green-100 text-green-800' },
      document: { label: 'Документ', color: 'bg-purple-100 text-purple-800' },
    };
    const badge = badges[source as keyof typeof badges] || { label: source, color: 'bg-gray-100 text-gray-800' };
    return (
      <span className={`px-2 py-1 text-xs rounded-full ${badge.color}`}>
        {badge.label}
      </span>
    );
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) {
      return <span className="ml-1 text-gray-400">⇅</span>;
    }
    return sortOrder === 'asc'
      ? <span className="ml-1">↑</span>
      : <span className="ml-1">↓</span>;
  };

  return (
    <div className="max-w-7xl mx-auto p-6 bg-white rounded-lg shadow-lg">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2 flex items-center">
          <span className="mr-3">📦</span>
          Истражување на цени по артикл
        </h1>
        <p className="text-gray-600">
          Пребарувајте цени на специфични производи и услуги низ сите тендери
        </p>
      </div>

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="mb-6">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <span className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400 text-xl">
              🔍
            </span>
            <input
              type="text"
              value={searchInput}
              onChange={handleInputChange}
              placeholder="Внесете назив на производ (пр. CT Scanner 64-slice)"
              className="w-full pl-12 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <button
            type="submit"
            disabled={loading || searchInput.length < 3}
            className="px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Пребарува...' : 'Барај'}
          </button>
        </div>
      </form>

      {/* Error Message */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          <strong>Грешка:</strong> {error}
        </div>
      )}

      {/* Statistics Cards */}
      {statistics && statistics.count > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center">
            <span className="mr-2">📊</span>
            Статистика ({statistics.count} резултати)
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-gradient-to-br from-green-50 to-green-100 p-4 rounded-lg border border-green-200">
              <div className="text-sm text-green-700 font-medium mb-1">Минимум</div>
              <div className="text-2xl font-bold text-green-900">
                {formatPrice(statistics.min_price)}
              </div>
            </div>
            <div className="bg-gradient-to-br from-red-50 to-red-100 p-4 rounded-lg border border-red-200">
              <div className="text-sm text-red-700 font-medium mb-1">Максимум</div>
              <div className="text-2xl font-bold text-red-900">
                {formatPrice(statistics.max_price)}
              </div>
            </div>
            <div className="bg-gradient-to-br from-blue-50 to-blue-100 p-4 rounded-lg border border-blue-200">
              <div className="text-sm text-blue-700 font-medium mb-1">Просек</div>
              <div className="text-2xl font-bold text-blue-900">
                {formatPrice(statistics.avg_price)}
              </div>
            </div>
            <div className="bg-gradient-to-br from-purple-50 to-purple-100 p-4 rounded-lg border border-purple-200">
              <div className="text-sm text-purple-700 font-medium mb-1">Медијана</div>
              <div className="text-2xl font-bold text-purple-900">
                {formatPrice(statistics.median_price)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Results Table */}
      {results.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center">
            <span className="mr-2">📋</span>
            Резултати
          </h2>
          <div className="overflow-x-auto border border-gray-200 rounded-lg">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th
                    onClick={() => sortResults('item_name')}
                    className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  >
                    Артикл <SortIcon field="item_name" />
                  </th>
                  <th
                    onClick={() => sortResults('unit_price')}
                    className="px-4 py-3 text-right text-xs font-medium text-gray-700 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  >
                    Единечна цена <SortIcon field="unit_price" />
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-700 uppercase tracking-wider">
                    Количина
                  </th>
                  <th
                    onClick={() => sortResults('tender_title')}
                    className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  >
                    Тендер <SortIcon field="tender_title" />
                  </th>
                  <th
                    onClick={() => sortResults('date')}
                    className="px-4 py-3 text-center text-xs font-medium text-gray-700 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  >
                    Датум <SortIcon field="date" />
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-700 uppercase tracking-wider">
                    Извор
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {results.map((result, idx) => (
                  <tr key={idx} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {result.item_name}
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-semibold text-gray-900">
                      {formatPrice(result.unit_price)}
                    </td>
                    <td className="px-4 py-3 text-sm text-center text-gray-600">
                      {result.quantity ? `${result.quantity} ${result.unit || ''}` : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <a
                        href={`/tenders/${encodeURIComponent(result.tender_id)}`}
                        className="text-blue-600 hover:underline line-clamp-2"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {result.tender_title}
                      </a>
                    </td>
                    <td className="px-4 py-3 text-sm text-center text-gray-600">
                      {formatDate(result.date)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {getSourceBadge(result.source)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* No Results */}
      {!loading && query && results.length === 0 && (
        <div className="text-center py-12">
          <div className="text-6xl mb-4">🔍</div>
          <h3 className="text-xl font-semibold text-gray-700 mb-2">
            Не се пронајдени резултати
          </h3>
          <p className="text-gray-500">
            Обидете се со поинаков термин за пребарување
          </p>
        </div>
      )}

      {/* Initial State */}
      {!loading && !query && (
        <div className="text-center py-12">
          <div className="text-6xl mb-4">💡</div>
          <h3 className="text-xl font-semibold text-gray-700 mb-2">
            Започнете со пребарување
          </h3>
          <p className="text-gray-500 mb-4">
            Внесете име на производ или услуга за да видите историски цени
          </p>
          <div className="flex flex-wrap gap-2 justify-center">
            <button
              onClick={() => {
                setSearchInput('CT Scanner');
                searchItems('CT Scanner');
              }}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            >
              CT Scanner
            </button>
            <button
              onClick={() => {
                setSearchInput('лаптоп');
                searchItems('лаптоп');
              }}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            >
              Лаптоп
            </button>
            <button
              onClick={() => {
                setSearchInput('канцелариски мебел');
                searchItems('канцелариски мебел');
              }}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            >
              Канцелариски мебел
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
