"use client";

import { useState, useMemo } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Search, FileText, ChevronDown, ChevronUp } from "lucide-react";
import { TenderDocument } from "@/lib/api";

interface DocumentSearchProps {
  documents: TenderDocument[];
}

interface SearchMatch {
  doc_id: string;
  file_name: string;
  matches: Array<{
    context: string;
    highlight: string;
  }>;
}

export function DocumentSearch({ documents }: DocumentSearchProps) {
  const [query, setQuery] = useState("");
  const [expandedDocs, setExpandedDocs] = useState<Set<string>>(new Set());

  // Find matches with context (50 chars before/after)
  const findMatchesWithContext = (text: string, searchQuery: string): Array<{ context: string; highlight: string }> => {
    if (!text || !searchQuery) return [];

    const lowerText = text.toLowerCase();
    const lowerQuery = searchQuery.toLowerCase();
    const matches: Array<{ context: string; highlight: string }> = [];

    let startIndex = 0;
    const CONTEXT_LENGTH = 50;
    const MAX_MATCHES = 5; // Limit matches per document

    while (startIndex < lowerText.length && matches.length < MAX_MATCHES) {
      const matchIndex = lowerText.indexOf(lowerQuery, startIndex);
      if (matchIndex === -1) break;

      // Extract context before and after
      const contextStart = Math.max(0, matchIndex - CONTEXT_LENGTH);
      const contextEnd = Math.min(text.length, matchIndex + lowerQuery.length + CONTEXT_LENGTH);

      let contextText = text.substring(contextStart, contextEnd);

      // Add ellipsis if truncated
      if (contextStart > 0) contextText = "..." + contextText;
      if (contextEnd < text.length) contextText = contextText + "...";

      matches.push({
        context: contextText,
        highlight: text.substring(matchIndex, matchIndex + lowerQuery.length)
      });

      startIndex = matchIndex + lowerQuery.length;
    }

    return matches;
  };

  // Search across all documents
  const searchResults = useMemo((): SearchMatch[] => {
    if (!query.trim()) return [];

    const results: SearchMatch[] = [];

    for (const doc of documents) {
      if (!doc.content_text) continue;

      const matches = findMatchesWithContext(doc.content_text, query);

      if (matches.length > 0) {
        results.push({
          doc_id: doc.doc_id,
          file_name: doc.file_name || "Unknown Document",
          matches
        });
      }
    }

    return results;
  }, [query, documents]);

  const toggleDocExpanded = (docId: string) => {
    setExpandedDocs(prev => {
      const newSet = new Set(prev);
      if (newSet.has(docId)) {
        newSet.delete(docId);
      } else {
        newSet.add(docId);
      }
      return newSet;
    });
  };

  // Highlight matching text
  const highlightText = (context: string, highlight: string) => {
    const parts = context.split(new RegExp(`(${highlight})`, 'gi'));
    return (
      <span>
        {parts.map((part, index) =>
          part.toLowerCase() === highlight.toLowerCase() ? (
            <mark key={index} className="bg-yellow-200 dark:bg-yellow-800 font-semibold">
              {part}
            </mark>
          ) : (
            <span key={index}>{part}</span>
          )
        )}
      </span>
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Search className="h-5 w-5" />
          Search Across All Documents
        </CardTitle>
        <CardDescription>
          Find text across all tender documents without downloading
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Search Input */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder='Search documents (e.g., "гаранција", "ISO", "цена")...'
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-10 pr-4"
          />
        </div>

        {/* Search Results */}
        {query.trim() ? (
          <div className="space-y-3">
            {searchResults.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <FileText className="h-12 w-12 mx-auto mb-2 opacity-20" />
                <p className="text-sm">No matches found for "{query}"</p>
                <p className="text-xs mt-1">Try different search terms</p>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">
                    Found in <Badge variant="secondary">{searchResults.length}</Badge> document
                    {searchResults.length !== 1 ? 's' : ''}
                  </p>
                </div>

                {searchResults.map((result) => {
                  const isExpanded = expandedDocs.has(result.doc_id);
                  const displayMatches = isExpanded ? result.matches : result.matches.slice(0, 2);

                  return (
                    <div
                      key={result.doc_id}
                      className="border rounded-lg p-4 space-y-2 bg-card hover:bg-accent/30 transition-colors"
                    >
                      {/* Document Header */}
                      <div className="flex items-start gap-2">
                        <FileText className="h-4 w-4 text-primary mt-1 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm truncate">{result.file_name}</p>
                          <p className="text-xs text-muted-foreground">
                            {result.matches.length} match{result.matches.length !== 1 ? 'es' : ''} found
                          </p>
                        </div>
                      </div>

                      {/* Matches */}
                      <div className="space-y-2 ml-6">
                        {displayMatches.map((match, index) => (
                          <div
                            key={index}
                            className="text-sm p-2 rounded bg-background/50 border-l-2 border-primary/30"
                          >
                            {highlightText(match.context, match.highlight)}
                          </div>
                        ))}

                        {/* Show More/Less Button */}
                        {result.matches.length > 2 && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => toggleDocExpanded(result.doc_id)}
                            className="w-full"
                          >
                            {isExpanded ? (
                              <>
                                <ChevronUp className="h-4 w-4 mr-2" />
                                Show less
                              </>
                            ) : (
                              <>
                                <ChevronDown className="h-4 w-4 mr-2" />
                                Show {result.matches.length - 2} more match
                                {result.matches.length - 2 !== 1 ? 'es' : ''}
                              </>
                            )}
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </>
            )}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            <Search className="h-12 w-12 mx-auto mb-2 opacity-20" />
            <p className="text-sm">Enter a search term to find text across all documents</p>
            <p className="text-xs mt-1">
              Searches through {documents.filter(d => d.content_text).length} document
              {documents.filter(d => d.content_text).length !== 1 ? 's' : ''} with extracted content
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
