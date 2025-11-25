"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ExportButton } from "@/components/ExportButton";
import { PriceHistoryChart } from "@/components/charts/PriceHistoryChart";
import { api, type ProductSearchResult, type ProductAggregation } from "@/lib/api";
import { Search, ChevronLeft, ChevronRight, Package, TrendingUp, Building2, Calendar, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

function formatPrice(price: number | undefined): string {
  if (!price) return "-";
  return new Intl.NumberFormat("mk-MK", {
    style: "currency",
    currency: "MKD",
    maximumFractionDigits: 0,
  }).format(price);
}

function formatQuantity(qty: number | undefined, unit: string | undefined): string {
  if (!qty) return "-";
  return `${qty.toLocaleString("mk-MK")} ${unit || ""}`.trim();
}

export default function ProductsPage() {
  const [query, setQuery] = useState("");
  const [products, setProducts] = useState<ProductSearchResult[]>([]);
  const [aggregations, setAggregations] = useState<ProductAggregation[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [stats, setStats] = useState<{
    total_products: number;
    tenders_with_products: number;
    unique_products: number;
  } | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const pageSize = 20;

  useEffect(() => {
    loadStats();
  }, []);

  async function loadStats() {
    try {
      const result = await api.getProductStats();
      setStats(result);
    } catch (error) {
      console.error("Failed to load product stats:", error);
    }
  }

  const searchProducts = useCallback(async (searchQuery: string, searchPage: number = 1) => {
    if (!searchQuery.trim()) {
      toast.error("Please enter a search term");
      return;
    }

    try {
      setLoading(true);
      setHasSearched(true);

      const [searchResult, aggResult] = await Promise.all([
        api.searchProducts({
          q: searchQuery,
          page: searchPage,
          page_size: pageSize,
        }),
        searchPage === 1 ? api.getProductAggregations(searchQuery) : Promise.resolve(null),
      ]);

      setProducts(searchResult.items);
      setTotal(searchResult.total);
      setPage(searchPage);

      if (aggResult) {
        setAggregations(aggResult.aggregations);
      }
    } catch (error) {
      console.error("Product search failed:", error);
      toast.error("Search failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    searchProducts(query, 1);
  };

  const handlePageChange = (newPage: number) => {
    searchProducts(query, newPage);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="p-4 md:p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold flex items-center gap-2">
          <Package className="h-8 w-8" />
          Product Search
        </h1>
        <p className="text-sm md:text-base text-muted-foreground mt-1">
          Search for specific products, medicines, equipment, and services across all tenders
        </p>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">{stats.total_products.toLocaleString()}</div>
              <p className="text-xs text-muted-foreground">Total Products</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">{stats.unique_products.toLocaleString()}</div>
              <p className="text-xs text-muted-foreground">Unique Products</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">{stats.tenders_with_products.toLocaleString()}</div>
              <p className="text-xs text-muted-foreground">Tenders with Products</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Search Form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Search Products</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSearch} className="flex gap-2">
            <Input
              placeholder="Search for products (e.g., paracetamol, intraocular lens, medical equipment...)"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1"
            />
            <Button type="submit" disabled={loading}>
              <Search className="h-4 w-4 mr-2" />
              Search
            </Button>
          </form>
          <div className="mt-2 flex flex-wrap gap-2">
            <span className="text-xs text-muted-foreground">Examples:</span>
            {["paracetamol", "intraocular lens", "medical equipment", "IT services"].map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => {
                  setQuery(example);
                  searchProducts(example, 1);
                }}
                className="text-xs text-primary hover:underline"
              >
                {example}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {hasSearched && (
        <>
          {/* Aggregations */}
          {aggregations.length > 0 && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <TrendingUp className="h-5 w-5" />
                    Price Analysis
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left p-2">Product</th>
                          <th className="text-right p-2">Avg. Price</th>
                          <th className="text-right p-2">Min Price</th>
                          <th className="text-right p-2">Max Price</th>
                          <th className="text-right p-2">Tenders</th>
                        </tr>
                      </thead>
                      <tbody>
                        {aggregations.slice(0, 5).map((agg, i) => (
                          <tr key={i} className="border-b last:border-0">
                            <td className="p-2 font-medium">{agg.product_name}</td>
                            <td className="text-right p-2">{formatPrice(agg.avg_unit_price)}</td>
                            <td className="text-right p-2 text-green-600">{formatPrice(agg.min_unit_price)}</td>
                            <td className="text-right p-2 text-red-600">{formatPrice(agg.max_unit_price)}</td>
                            <td className="text-right p-2">{agg.tender_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>

              {/* Price History Chart - Sample data for demonstration */}
              {aggregations.length > 0 && aggregations[0].years && aggregations[0].years.length > 0 && (
                <PriceHistoryChart
                  data={aggregations[0].years.map((year) => ({
                    period: year.toString(),
                    avg_estimated: aggregations[0].avg_unit_price || 0,
                    avg_awarded: (aggregations[0].avg_unit_price || 0) * 0.95, // Mock data - 5% lower
                    count: aggregations[0].tender_count,
                  }))}
                  title={`Историја на цени - ${aggregations[0].product_name}`}
                />
              )}
            </>
          )}

          {/* Results Header */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {total.toLocaleString()} results for "{query}"
            </p>
            <div className="flex items-center gap-2">
              {totalPages > 1 && (
                <p className="text-sm text-muted-foreground">
                  Page {page} of {totalPages}
                </p>
              )}
              {products.length > 0 && (
                <ExportButton
                  data={products}
                  filename={`products-${query.replace(/\s+/g, '-')}-${new Date().toISOString().split('T')[0]}`}
                  columns={[
                    { key: 'name', label: 'Product Name' },
                    { key: 'quantity', label: 'Quantity' },
                    { key: 'unit', label: 'Unit' },
                    { key: 'unit_price', label: 'Unit Price (MKD)' },
                    { key: 'total_price', label: 'Total Price (MKD)' },
                    { key: 'cpv_code', label: 'CPV Code' },
                    { key: 'tender_title', label: 'Tender' },
                    { key: 'procuring_entity', label: 'Entity' },
                    { key: 'opening_date', label: 'Date' },
                  ]}
                />
              )}
            </div>
          </div>

          {/* Product Cards */}
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-muted-foreground">Loading...</p>
            </div>
          ) : products.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Package className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No products found for "{query}"</p>
              <p className="text-xs text-muted-foreground mt-1">
                Try different search terms or check spelling
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {products.map((product) => (
                <Card key={product.id} className="hover:border-primary/50 transition-colors">
                  <CardContent className="pt-6">
                    <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                      {/* Product Info */}
                      <div className="flex-1 space-y-2">
                        <h3 className="font-semibold text-lg">{product.name}</h3>

                        <div className="flex flex-wrap gap-2 text-sm">
                          {product.quantity && (
                            <Badge variant="secondary">
                              Qty: {formatQuantity(product.quantity, product.unit)}
                            </Badge>
                          )}
                          {product.unit_price && (
                            <Badge variant="outline">
                              Unit: {formatPrice(product.unit_price)}
                            </Badge>
                          )}
                          {product.total_price && (
                            <Badge className="bg-green-100 text-green-800 hover:bg-green-200">
                              Total: {formatPrice(product.total_price)}
                            </Badge>
                          )}
                          {product.cpv_code && (
                            <Badge variant="outline" className="font-mono">
                              CPV: {product.cpv_code}
                            </Badge>
                          )}
                        </div>

                        {/* Tender Context */}
                        <div className="pt-2 border-t mt-2">
                          <div className="flex items-start gap-2 text-sm text-muted-foreground">
                            <Building2 className="h-4 w-4 mt-0.5 shrink-0" />
                            <div>
                              <p className="font-medium text-foreground">
                                {product.tender_title || "Untitled Tender"}
                              </p>
                              <p>{product.procuring_entity}</p>
                            </div>
                          </div>

                          <div className="flex flex-wrap gap-4 mt-2 text-xs text-muted-foreground">
                            {product.opening_date && (
                              <span className="flex items-center gap-1">
                                <Calendar className="h-3 w-3" />
                                {new Date(product.opening_date).toLocaleDateString("mk-MK")}
                              </span>
                            )}
                            {product.status && (
                              <Badge variant="outline" className="text-xs">
                                {product.status}
                              </Badge>
                            )}
                            {product.winner && (
                              <span className="text-green-600">
                                Winner: {product.winner}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex md:flex-col gap-2">
                        <Link href={`/tenders/${encodeURIComponent(product.tender_id)}`}>
                          <Button variant="outline" size="sm">
                            <ExternalLink className="h-4 w-4 mr-1" />
                            View Tender
                          </Button>
                        </Link>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-4 pt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(page - 1)}
                disabled={page === 1 || loading}
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(page + 1)}
                disabled={page === totalPages || loading}
              >
                Next
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
