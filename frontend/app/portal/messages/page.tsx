'use client';

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import MessageThread from '@/components/bid-service/MessageThread';
import { api } from '@/lib/api';
import type { BidMessage } from '@/lib/bid-service-types';

export default function PortalMessagesPage() {
  const [messages, setMessages] = useState<BidMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.getGeneralMessages();
      setMessages(res.messages);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Грешка при вчитување.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleSend = async (body: string) => {
    const res = await api.sendGeneralMessage(body);
    setMessages((prev) => [...prev, res.message]);
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4 md:p-6">
      <div>
        <h1 className="text-2xl font-bold">Пораки</h1>
        <p className="text-sm text-muted-foreground">
          Општ разговор со тимот на НабавкиДата. За прашања поврзани со конкретна понуда пишете во самата понуда.
        </p>
      </div>
      {error && (
        <Card>
          <CardContent className="py-4 text-sm text-destructive">{error}</CardContent>
        </Card>
      )}
      {loading ? (
        <p className="py-12 text-center text-sm text-muted-foreground">Се вчитува…</p>
      ) : (
        <Card>
          <CardContent className="p-4">
            <MessageThread
              messages={messages}
              viewerRole="client"
              onSend={handleSend}
              emptyText="Сè уште нема пораки. Пишете ни што ви треба."
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
