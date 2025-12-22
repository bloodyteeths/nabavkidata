"use client";

import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Search, Loader2, Plus, Star } from "lucide-react";

interface SearchResult {
  company_name: string;
  total_wins: number;
  total_bids: number;
  total_contract_value: number | null;
}

interface CompetitorSearchProps {
  onSearch: (query: string) => Promise<SearchResult[]>;
  onAddCompetitor: (companyName: string) => void;
  trackedCompetitors: string[];
  isTrackingLoading?: string | null;
}

export function CompetitorSearch({
  onSearch,
  onAddCompetitor,
  trackedCompetitors,
  isTrackingLoading,
}: CompetitorSearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showResults, setShowResults] = useState(false);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(async () => {
      if (query.length >= 2) {
        setIsSearching(true);
        try {
          const searchResults = await onSearch(query);
          setResults(searchResults);
          setShowResults(true);
        } catch (error) {
          console.error("Search failed:", error);
          setResults([]);
        } finally {
          setIsSearching(false);
        }
      } else {
        setResults([]);
        setShowResults(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query, onSearch]);

  const isTracked = (companyName: string): boolean => {
    return trackedCompetitors.some(
      (c) => c.toLowerCase() === companyName.toLowerCase()
    );
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Search className="h-4 w-4" />
          Пребарај компании
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative">
          {/* Search Input */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Внесете име на компанија за пребарување..."
              className="pl-9"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => query.length >= 2 && setShowResults(true)}
              onBlur={() => setTimeout(() => setShowResults(false), 200)}
            />
            {isSearching && (
              <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />
            )}
          </div>

          {/* Search Results Dropdown */}
          {showResults && results.length > 0 && (
            <div className="absolute z-[100] w-full mt-1 max-h-64 overflow-auto border rounded-md bg-background shadow-lg">
              {results.map((result) => {
                const tracked = isTracked(result.company_name);
                return (
                  <div
                    key={result.company_name}
                    className="flex items-center justify-between px-3 py-2 hover:bg-accent border-b last:border-0"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">
                        {result.company_name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {result.total_wins} победи · {result.total_bids} понуди
                        {result.total_contract_value &&
                          ` · ${(result.total_contract_value / 1_000_000).toFixed(1)}M МКД`}
                      </p>
                    </div>
                    <Button
                      variant={tracked ? "secondary" : "default"}
                      size="sm"
                      className="ml-2 flex-shrink-0"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        onAddCompetitor(result.company_name);
                      }}
                      disabled={isTrackingLoading === result.company_name}
                    >
                      {isTrackingLoading === result.company_name ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : tracked ? (
                        <>
                          <Star className="h-4 w-4 mr-1 fill-yellow-500 text-yellow-500" />
                          Следена
                        </>
                      ) : (
                        <>
                          <Plus className="h-4 w-4 mr-1" />
                          Следи
                        </>
                      )}
                    </Button>
                  </div>
                );
              })}
            </div>
          )}

          {/* No Results */}
          {showResults &&
            query.length >= 2 &&
            results.length === 0 &&
            !isSearching && (
              <div className="absolute z-[100] w-full mt-1 border rounded-md bg-background shadow-lg p-4 text-center text-sm text-muted-foreground">
                Нема резултати за „{query}"
              </div>
            )}
        </div>
      </CardContent>
    </Card>
  );
}
