"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  FileText,
  FileSpreadsheet,
  FileType,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  AlertCircle,
} from "lucide-react";

/**
 * Source document with metadata
 */
export interface Source {
  doc_id?: string;
  tender_id?: string;
  file_name?: string;
  excerpt?: string;
  chunk_text?: string;  // Alternative to excerpt
  similarity?: number;
  relevance?: number;
  title?: string;  // Tender title
  category?: string;  // Tender category
}

/**
 * Props for SourceCitation component
 */
export interface SourceCitationProps {
  sources: Source[];
  onViewDocument?: (docId: string, fileName?: string) => void;
  maxVisible?: number;  // Default 3
  showConfidence?: boolean;  // Show confidence badge
  confidence?: string;  // 'high', 'medium', 'low'
}

/**
 * Get file type icon based on filename extension
 */
function getFileIcon(fileName?: string) {
  if (!fileName) return <FileText className="h-4 w-4 text-gray-500" />;

  const ext = fileName.split('.').pop()?.toLowerCase();

  if (ext === 'pdf') {
    return <FileText className="h-4 w-4 text-red-600" />;
  } else if (ext === 'doc' || ext === 'docx') {
    return <FileType className="h-4 w-4 text-blue-600" />;
  } else if (ext === 'xls' || ext === 'xlsx') {
    return <FileSpreadsheet className="h-4 w-4 text-green-600" />;
  }

  return <FileText className="h-4 w-4 text-gray-500" />;
}

/**
 * Truncate text to specified length with ellipsis
 */
function truncateText(text: string, maxLength: number = 100): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength).trim() + '...';
}

/**
 * Get confidence badge color and label
 */
function getConfidenceBadge(confidence?: string) {
  if (!confidence) return null;

  const confidenceLower = confidence.toLowerCase();

  if (confidenceLower === 'high' || confidenceLower === 'висока') {
    return (
      <Badge variant="default" className="bg-green-100 text-green-800 border-green-300">
        Висока сигурност
      </Badge>
    );
  } else if (confidenceLower === 'medium' || confidenceLower === 'средна') {
    return (
      <Badge variant="default" className="bg-yellow-100 text-yellow-800 border-yellow-300">
        Средна сигурност
      </Badge>
    );
  } else if (confidenceLower === 'low' || confidenceLower === 'ниска') {
    return (
      <Badge variant="default" className="bg-red-100 text-red-800 border-red-300">
        Ниска сигурност
      </Badge>
    );
  }

  return null;
}

/**
 * Format similarity/relevance score as percentage
 */
function formatRelevance(source: Source): string {
  const score = source.similarity ?? source.relevance;
  if (score === undefined || score === null) return '';

  // If score is between 0 and 1, convert to percentage
  const percentage = score <= 1 ? Math.round(score * 100) : Math.round(score);
  return `${percentage}%`;
}

/**
 * SourceCitation Component
 *
 * Displays document sources cited by AI in responses
 * Each source shows file name, excerpt, and click-to-view functionality
 */
export function SourceCitation({
  sources,
  onViewDocument,
  maxVisible = 3,
  showConfidence = false,
  confidence,
}: SourceCitationProps) {
  const [expanded, setExpanded] = useState(false);

  // Filter out sources without meaningful data
  const validSources = sources.filter(
    (source) => source.doc_id || source.tender_id || source.file_name
  );

  if (validSources.length === 0) {
    return null;
  }

  // Determine how many sources to show
  const visibleSources = expanded
    ? validSources
    : validSources.slice(0, maxVisible);
  const hasMore = validSources.length > maxVisible;

  return (
    <Card className="border border-primary/20 bg-primary/5 mt-3">
      <CardContent className="p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold text-primary">ИЗВОРИ</h3>
            <Badge variant="secondary" className="text-xs">
              {validSources.length}
            </Badge>
          </div>
          {showConfidence && confidence && (
            <div>{getConfidenceBadge(confidence)}</div>
          )}
        </div>

        {/* Source List */}
        <div className="space-y-2">
          {visibleSources.map((source, index) => {
            const excerpt = source.excerpt || source.chunk_text || '';
            const fileName = source.file_name || source.title || `Документ ${index + 1}`;
            const relevanceScore = formatRelevance(source);

            return (
              <div
                key={source.doc_id || source.tender_id || index}
                className="rounded-lg border bg-white dark:bg-gray-800 p-3 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start gap-3">
                  {/* File Icon */}
                  <div className="flex-shrink-0 mt-1">
                    {getFileIcon(source.file_name)}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    {/* File Name */}
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <h4 className="text-sm font-medium text-foreground truncate">
                        {fileName}
                      </h4>
                      {relevanceScore && (
                        <Badge variant="outline" className="text-xs flex-shrink-0">
                          {relevanceScore}
                        </Badge>
                      )}
                    </div>

                    {/* Category/Tender Info */}
                    {(source.category || source.tender_id) && (
                      <div className="flex flex-wrap gap-1 mb-2">
                        {source.category && (
                          <Badge variant="secondary" className="text-xs">
                            {source.category}
                          </Badge>
                        )}
                        {source.tender_id && (
                          <Badge variant="outline" className="text-xs">
                            ID: {source.tender_id}
                          </Badge>
                        )}
                      </div>
                    )}

                    {/* Excerpt */}
                    {excerpt && (
                      <p className="text-xs text-muted-foreground leading-relaxed mb-2">
                        "{truncateText(excerpt, 150)}"
                      </p>
                    )}

                    {/* View Button */}
                    {onViewDocument && source.doc_id && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs"
                        onClick={() => onViewDocument(source.doc_id!, source.file_name)}
                      >
                        <ExternalLink className="h-3 w-3 mr-1" />
                        Отвори
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Expand/Collapse Button */}
        {hasMore && (
          <Button
            variant="ghost"
            size="sm"
            className="w-full mt-3 text-xs"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? (
              <>
                <ChevronUp className="h-3 w-3 mr-1" />
                Прикажи помалку
              </>
            ) : (
              <>
                <ChevronDown className="h-3 w-3 mr-1" />
                Прикажи уште {validSources.length - maxVisible} извори
              </>
            )}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
