import { Avatar } from "@/components/ui/avatar";
import { Card } from "@/components/ui/card";
import { Bot, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { SourceCitation, Source } from "@/components/ai/SourceCitation";

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
  onViewDocument?: (docId: string, fileName?: string) => void;
}

export function ChatMessage({ role, content, sources, confidence, onViewDocument }: ChatMessageProps) {
  const isUser = role === "user";

  // Convert sources to Source type for SourceCitation component
  const formattedSources: Source[] = sources?.map(s => ({
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

  return (
    <div className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <Avatar className="h-8 w-8 bg-primary flex items-center justify-center">
          <Bot className="h-4 w-4 text-primary-foreground" />
        </Avatar>
      )}

      <div className={cn("max-w-[80%] space-y-2", isUser && "flex flex-col items-end")}>
        <Card className={cn(
          "p-3",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        )}>
          <p className="text-sm whitespace-pre-wrap">{content}</p>
        </Card>

        {/* Use SourceCitation component for assistant messages */}
        {!isUser && formattedSources.length > 0 && (
          <SourceCitation
            sources={formattedSources}
            onViewDocument={onViewDocument}
            maxVisible={3}
            showConfidence={true}
            confidence={confidence}
          />
        )}
      </div>

      {isUser && (
        <Avatar className="h-8 w-8 bg-secondary flex items-center justify-center">
          <User className="h-4 w-4 text-secondary-foreground" />
        </Avatar>
      )}
    </div>
  );
}
