"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  FileText,
  Download,
  Copy,
  ChevronDown,
  ChevronUp,
  Search,
  Sparkles,
  CheckCircle2,
  X,
} from "lucide-react";
import { toast } from "sonner";

export interface DocumentViewerProps {
  docId: string;
  fileName: string;
  fileUrl?: string;
  contentText?: string;
  onClose?: () => void;
}

interface DocumentContent {
  content_text: string;
  ai_summary?: string;
  key_requirements?: string[];
  items_mentioned?: string[];
}

export function DocumentViewer({
  docId,
  fileName,
  fileUrl,
  contentText,
  onClose,
}: DocumentViewerProps) {
  const [expanded, setExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [documentContent, setDocumentContent] = useState<DocumentContent | null>(
    contentText ? { content_text: contentText } : null
  );
  const [copied, setCopied] = useState(false);

  // Load full document content if not already loaded
  const loadDocumentContent = async () => {
    // If we already have content (passed as prop), don't fetch again
    if (documentContent?.content_text) return;

    setLoading(true);
    try {
      const { api } = await import("@/lib/api");
      const result = await api.getDocumentContent(docId);
      if (result && result.content_text) {
        setDocumentContent(result);
      } else {
        // No content available
        setDocumentContent({ content_text: "" });
      }
    } catch (error: any) {
      console.error("Failed to load document content:", error);
      // Don't show toast for expected cases like 404
      if (error?.message?.includes("404")) {
        // Document content not available - silently handle
      } else {
        toast.error("Не успеавме да ја вчитаме содржината");
      }
      // If API fails, show empty state
      setDocumentContent({ content_text: "" });
    } finally {
      setLoading(false);
    }
  };

  // Highlight search matches in text
  const highlightText = (text: string, query: string) => {
    if (!query.trim() || !text) return text;

    try {
      // Escape special regex characters to prevent crash
      const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(`(${escapedQuery})`, "gi");
      const parts = text.split(regex);

      return parts.map((part, index) =>
        regex.test(part) ? (
          <mark key={index} className="bg-yellow-200 dark:bg-yellow-800">
            {part}
          </mark>
        ) : (
          <span key={index}>{part}</span>
        )
      );
    } catch (error) {
      // If regex fails for any reason, return plain text
      console.error("Highlight text error:", error);
      return text;
    }
  };

  // Copy text to clipboard
  const handleCopyText = async () => {
    if (!documentContent?.content_text) return;

    try {
      await navigator.clipboard.writeText(documentContent.content_text);
      setCopied(true);
      toast.success("Текстот е копиран");
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      toast.error("Не успеавме да го копираме текстот");
    }
  };

  // Download document
  const handleDownload = () => {
    if (!fileUrl) return;
    window.open(fileUrl, "_blank", "noopener,noreferrer");
  };

  return (
    <Card className="border-2">
      {/* Header */}
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <FileText className="h-5 w-5 text-primary flex-shrink-0 mt-1" />
            <div className="flex-1 min-w-0">
              <CardTitle className="text-base truncate">{fileName}</CardTitle>
              <p className="text-xs text-muted-foreground mt-1">
                Документ ID: {docId}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {fileUrl && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownload}
              >
                <Download className="h-4 w-4 mr-1" />
                Преземи
              </Button>
            )}
            {onClose && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onClose}
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* AI Summary Section */}
        {documentContent?.ai_summary && (
          <div className="rounded-lg bg-primary/5 border border-primary/20 p-4">
            <div className="flex items-start gap-2 mb-3">
              <Sparkles className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
              <h3 className="text-sm font-semibold text-primary">AI РЕЗИМЕ</h3>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {documentContent.ai_summary}
            </p>
          </div>
        )}

        {/* Key Requirements Section */}
        {documentContent?.key_requirements && documentContent.key_requirements.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <h3 className="text-sm font-semibold">КЛУЧНИ БАРАЊА</h3>
            </div>
            <ul className="space-y-1.5">
              {documentContent.key_requirements.map((req, idx) => (
                <li key={idx} className="text-sm flex items-start gap-2">
                  <span className="text-primary mt-0.5">•</span>
                  <span className="flex-1">{req}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Items Mentioned Section */}
        {documentContent?.items_mentioned && documentContent.items_mentioned.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold mb-2">СПОМЕНАТИ ПРОИЗВОДИ/УСЛУГИ</h3>
            <div className="flex flex-wrap gap-2">
              {documentContent.items_mentioned.map((item, idx) => (
                <Badge key={idx} variant="secondary">
                  {item}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Full Document Text Section */}
        <div className="border-t pt-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <FileText className="h-4 w-4" />
              ЦЕЛОСЕН ТЕКСТ
            </h3>
            <div className="flex items-center gap-2">
              {documentContent?.content_text && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCopyText}
                >
                  {copied ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  if (!expanded && !documentContent?.content_text) {
                    loadDocumentContent();
                  }
                  setExpanded(!expanded);
                }}
              >
                {expanded ? (
                  <>
                    <ChevronUp className="h-4 w-4 mr-1" />
                    Склопи
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-4 w-4 mr-1" />
                    Прошири
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Search Bar (only when expanded) */}
          {expanded && documentContent?.content_text && (
            <div className="mb-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Пребарај во документот..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
          )}

          {/* Content Display */}
          {expanded && (
            <div className="rounded-lg border bg-muted/30 p-4 max-h-[600px] overflow-y-auto">
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
                </div>
              ) : documentContent?.content_text ? (
                <div className="text-sm whitespace-pre-wrap leading-relaxed font-mono">
                  {highlightText(documentContent.content_text, searchQuery)}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <FileText className="h-12 w-12 mx-auto mb-2 opacity-20" />
                  <p className="text-sm">
                    Содржината на документот не е достапна
                  </p>
                  <p className="text-xs mt-1">
                    Користете го копчето за превземање за да го отворите документот
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Preview when collapsed */}
          {!expanded && documentContent?.content_text && (
            <div className="rounded-lg border bg-muted/30 p-4">
              <p className="text-sm text-muted-foreground line-clamp-3">
                {documentContent.content_text}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                Кликни "Прошири" за да го видиш целосниот текст
              </p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
