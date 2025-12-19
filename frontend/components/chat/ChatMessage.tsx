"use client";

import { useState } from "react";
import { Avatar } from "@/components/ui/avatar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Bot, User, Copy, Check, ThumbsUp, ThumbsDown, ExternalLink, Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import { SourceCitation, Source } from "@/components/ai/SourceCitation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Link from "next/link";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  sources?: Array<{
    tender_id?: string;
    doc_id?: string;
    chunk_text?: string;
    excerpt?: string;
    file_name?: string;
    similarity?: number;
    relevance?: number;
    title?: string;
    category?: string;
  }>;
  confidence?: string;
  timestamp?: string | Date;
  onViewDocument?: (docId: string, fileName?: string) => void;
  onFeedback?: (messageId: string, helpful: boolean) => void;
  messageId?: string;
}

/**
 * Regex to match Macedonian tender IDs: 5 digits / 4 digits (e.g., 21555/2021, 00362/2019)
 */
const TENDER_ID_REGEX = /\b(\d{4,5}\/\d{4})\b/g;

/**
 * Parse content and replace tender IDs with clickable links
 */
function linkifyTenderIds(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;

  const regex = new RegExp(TENDER_ID_REGEX.source, 'g');

  while ((match = regex.exec(text)) !== null) {
    // Add text before the match
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }

    // Add the tender link
    const tenderId = match[1];
    parts.push(
      <Link
        key={`tender-${match.index}`}
        href={`/tenders/${encodeURIComponent(tenderId)}`}
        className="inline-flex items-center gap-1 text-primary hover:underline font-medium"
      >
        {tenderId}
        <ExternalLink className="h-3 w-3" />
      </Link>
    );

    lastIndex = regex.lastIndex;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }

  return parts.length > 0 ? parts : [text];
}

/**
 * Format timestamp for display
 */
function formatTimestamp(timestamp?: string | Date): string {
  if (!timestamp) return "";
  const date = typeof timestamp === "string" ? new Date(timestamp) : timestamp;
  return date.toLocaleTimeString("mk-MK", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Custom markdown components that linkify tender IDs
 */
const markdownComponents = {
  p: ({ children, ...props }: any) => {
    // If children is a string, linkify tender IDs
    if (typeof children === "string") {
      return <p {...props}>{linkifyTenderIds(children)}</p>;
    }
    // If children is an array, process each child
    if (Array.isArray(children)) {
      return (
        <p {...props}>
          {children.map((child, i) =>
            typeof child === "string" ? (
              <span key={i}>{linkifyTenderIds(child)}</span>
            ) : (
              child
            )
          )}
        </p>
      );
    }
    return <p {...props}>{children}</p>;
  },
  // Style links
  a: ({ href, children, ...props }: any) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary hover:underline inline-flex items-center gap-1"
      {...props}
    >
      {children}
      <ExternalLink className="h-3 w-3" />
    </a>
  ),
  // Style tables
  table: ({ children, ...props }: any) => (
    <div className="overflow-x-auto my-2">
      <table className="min-w-full text-xs border-collapse" {...props}>
        {children}
      </table>
    </div>
  ),
  th: ({ children, ...props }: any) => (
    <th className="border border-border px-2 py-1 bg-muted font-medium text-left" {...props}>
      {children}
    </th>
  ),
  td: ({ children, ...props }: any) => (
    <td className="border border-border px-2 py-1" {...props}>
      {children}
    </td>
  ),
  // Style lists
  ul: ({ children, ...props }: any) => (
    <ul className="list-disc list-inside space-y-1 my-2" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }: any) => (
    <ol className="list-decimal list-inside space-y-1 my-2" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }: any) => {
    // Linkify tender IDs in list items
    if (typeof children === "string") {
      return <li {...props}>{linkifyTenderIds(children)}</li>;
    }
    return <li {...props}>{children}</li>;
  },
  // Style headings
  h1: ({ children, ...props }: any) => (
    <h1 className="text-lg font-bold mt-4 mb-2" {...props}>{children}</h1>
  ),
  h2: ({ children, ...props }: any) => (
    <h2 className="text-base font-bold mt-3 mb-2" {...props}>{children}</h2>
  ),
  h3: ({ children, ...props }: any) => (
    <h3 className="text-sm font-semibold mt-2 mb-1" {...props}>{children}</h3>
  ),
  // Style code blocks
  code: ({ inline, children, ...props }: any) => {
    if (inline) {
      return (
        <code className="bg-muted px-1 py-0.5 rounded text-xs" {...props}>
          {children}
        </code>
      );
    }
    return (
      <pre className="bg-muted p-2 rounded text-xs overflow-x-auto my-2">
        <code {...props}>{children}</code>
      </pre>
    );
  },
  // Style blockquotes
  blockquote: ({ children, ...props }: any) => (
    <blockquote className="border-l-2 border-primary pl-3 italic my-2 text-muted-foreground" {...props}>
      {children}
    </blockquote>
  ),
  // Bold text - also linkify
  strong: ({ children, ...props }: any) => {
    if (typeof children === "string") {
      return <strong {...props}>{linkifyTenderIds(children)}</strong>;
    }
    return <strong {...props}>{children}</strong>;
  },
};

export function ChatMessage({
  role,
  content,
  sources,
  confidence,
  timestamp,
  onViewDocument,
  onFeedback,
  messageId,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const isUser = role === "user";

  // Convert sources to Source type for SourceCitation component
  const formattedSources: Source[] =
    sources?.map((s) => ({
      doc_id: s.doc_id,
      tender_id: s.tender_id,
      file_name: s.file_name,
      excerpt: s.excerpt || s.chunk_text,
      chunk_text: s.chunk_text,
      similarity: s.similarity,
      relevance: s.relevance,
      title: s.title,
      category: s.category,
    })) || [];

  // Handle copy to clipboard
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  // Handle feedback
  const handleFeedback = (helpful: boolean) => {
    const newFeedback = helpful ? "up" : "down";
    setFeedback(newFeedback);
    if (onFeedback && messageId) {
      onFeedback(messageId, helpful);
    }
  };

  return (
    <div className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <Avatar className="h-8 w-8 bg-primary flex items-center justify-center flex-shrink-0">
          <Bot className="h-4 w-4 text-primary-foreground" />
        </Avatar>
      )}

      <div className={cn("max-w-[85%] space-y-2", isUser && "flex flex-col items-end")}>
        {/* Timestamp */}
        {timestamp && (
          <div className={cn("flex items-center gap-1 text-[10px] text-muted-foreground", isUser && "justify-end")}>
            <Clock className="h-2.5 w-2.5" />
            {formatTimestamp(timestamp)}
          </div>
        )}

        <Card
          className={cn(
            "p-3 relative group",
            isUser ? "bg-primary text-primary-foreground" : "bg-muted"
          )}
        >
          {/* Message Content */}
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap">{content}</p>
          ) : (
            <div className="text-sm prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents}
              >
                {content}
              </ReactMarkdown>
            </div>
          )}

          {/* Action Buttons for Assistant Messages */}
          {!isUser && (
            <div className="flex items-center gap-1 mt-3 pt-2 border-t border-border/50">
              {/* Copy Button */}
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs gap-1 text-muted-foreground hover:text-foreground"
                onClick={handleCopy}
              >
                {copied ? (
                  <>
                    <Check className="h-3 w-3 text-green-500" />
                    <span className="text-green-500">Копирано!</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3" />
                    Копирај
                  </>
                )}
              </Button>

              {/* Feedback Buttons */}
              <div className="flex items-center gap-1 ml-auto">
                <span className="text-[10px] text-muted-foreground mr-1">Корисно?</span>
                <Button
                  variant="ghost"
                  size="sm"
                  className={cn(
                    "h-7 w-7 p-0",
                    feedback === "up" && "bg-green-100 text-green-600 hover:bg-green-100"
                  )}
                  onClick={() => handleFeedback(true)}
                >
                  <ThumbsUp className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className={cn(
                    "h-7 w-7 p-0",
                    feedback === "down" && "bg-red-100 text-red-600 hover:bg-red-100"
                  )}
                  onClick={() => handleFeedback(false)}
                >
                  <ThumbsDown className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          )}
        </Card>

        {/* Source Citations for Assistant Messages */}
        {!isUser && formattedSources.length > 0 && (
          <SourceCitation
            sources={formattedSources}
            onViewDocument={onViewDocument}
            maxVisible={3}
            showConfidence={!!confidence}
            confidence={confidence}
          />
        )}
      </div>

      {isUser && (
        <Avatar className="h-8 w-8 bg-secondary flex items-center justify-center flex-shrink-0">
          <User className="h-4 w-4 text-secondary-foreground" />
        </Avatar>
      )}
    </div>
  );
}
