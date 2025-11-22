import { Avatar } from "@/components/ui/avatar";
import { Card } from "@/components/ui/card";
import { Bot, User } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  sources?: Array<{
    tender_id?: string;
    doc_id?: string;
    chunk_text: string;
    similarity: number;
  }>;
}

export function ChatMessage({ role, content, sources }: ChatMessageProps) {
  const isUser = role === "user";

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

        {sources && sources.length > 0 && (
          <div className="text-xs text-muted-foreground space-y-1">
            <p className="font-medium">Извори:</p>
            {sources.slice(0, 3).map((source, idx) => (
              <div key={idx} className="pl-2 border-l-2 border-muted">
                <p className="line-clamp-2">{source.chunk_text}</p>
                <p className="text-xs opacity-70">
                  Сличност: {Math.round(source.similarity * 100)}%
                </p>
              </div>
            ))}
          </div>
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
