'use client';

import { useEffect, useRef, useState } from 'react';
import { Loader2, Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import type { BidMessage } from '@/lib/bid-service-types';
import { formatDmyTime } from '@/components/bid-service/DeadlineWarning';

interface MessageThreadProps {
  messages: BidMessage[];
  viewerRole: 'client' | 'admin';
  onSend: (body: string) => Promise<void>;
  emptyText?: string;
  className?: string;
}

const MAX_BODY = 5000;

/** Presentational message thread: own bubbles on the right, the other side on the left. */
export default function MessageThread({
  messages,
  viewerRole,
  onSend,
  emptyText = 'Сè уште нема пораки.',
  className,
}: MessageThreadProps) {
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  const trimmed = body.trim();

  const send = async () => {
    if (!trimmed || sending) return;
    setSending(true);
    setError(null);
    try {
      await onSend(trimmed);
      setBody('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Пораката не е испратена. Обидете се повторно.');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className={cn('flex flex-col gap-3', className)}>
      <div ref={listRef} className="max-h-[480px] space-y-3 overflow-y-auto pr-1">
        {messages.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">{emptyText}</p>
        ) : (
          messages.map((m) => {
            const own = m.sender_role === viewerRole;
            const name =
              m.sender_name || (m.sender_role === 'admin' ? 'Тимот на НабавкиДата' : 'Клиент');
            return (
              <div key={m.id} className={cn('flex', own ? 'justify-end' : 'justify-start')}>
                <div
                  className={cn(
                    'max-w-[85%] rounded-lg px-3 py-2 text-sm',
                    own
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-foreground'
                  )}
                >
                  <div
                    className={cn(
                      'mb-1 flex flex-wrap gap-x-2 text-xs',
                      own ? 'text-primary-foreground/80' : 'text-muted-foreground'
                    )}
                  >
                    <span className="font-medium">{own ? 'Вие' : name}</span>
                    <span>{formatDmyTime(m.created_at)}</span>
                  </div>
                  <p className="whitespace-pre-wrap break-words">{m.body}</p>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="space-y-2">
        <Textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Напишете порака…"
          rows={3}
          maxLength={MAX_BODY}
          disabled={sending}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              void send();
            }
          }}
        />
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <div className="flex justify-end">
          <Button onClick={send} disabled={sending || !trimmed}>
            {sending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Send className="mr-2 h-4 w-4" />
            )}
            Испрати
          </Button>
        </div>
      </div>
    </div>
  );
}
