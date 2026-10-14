'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Search } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import MatchedTenderCard from '@/components/bid-service/MatchedTenderCard';
import KeywordsEditor from '@/components/bid-service/KeywordsEditor';
import { api } from '@/lib/api';
import { tenderUrl } from '@/lib/utils';
import type { MatchedTender } from '@/lib/bid-service-types';

const TENDER_NO_RE = /^\s*(\d{1,6})\s*\/\s*(\d{4})\s*$/;

/** Jump straight to a tender the client already knows by number (e.g. 17400/2026). */
function TenderNumberSearch() {
  const router = useRouter();
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);

  const go = (e: React.FormEvent) => {
    e.preventDefault();
    const m = TENDER_NO_RE.exec(value);
    if (!m) {
      setError('Внесете број на тендер во облик 17400/2026.');
      return;
    }
    setError(null);
    router.push(`${tenderUrl(`${m[1]}/${m[2]}`)}?ponuda=1`);
  };

  return (
    <form onSubmit={go} className="space-y-2">
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Број на тендер, на пр. 17400/2026"
          inputMode="numeric"
        />
        <Button type="submit">Отвори тендер</Button>
      </div>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      <p className="text-xs text-muted-foreground">
        Или{' '}
        <Link href="/tenders" className="text-primary underline underline-offset-4">
          пребарајте ги сите отворени тендери
        </Link>{' '}
        и кликнете „Започни понуда“ на тендерот што ве интересира.
      </p>
    </form>
  );
}

export default function PortalTendersPage() {
  const [tenders, setTenders] = useState<MatchedTender[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getPortalMatchedTenders(50);
      setTenders(res.tenders);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Грешка при вчитување.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div>
        <h1 className="text-2xl font-bold">Тендери за мене</h1>
        <p className="text-sm text-muted-foreground">
          Отворени тендери што одговараат на вашиот профил. Изберете тендер и ние ја подготвуваме понудата.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Знаете кој тендер ви треба?</CardTitle>
          </CardHeader>
          <CardContent>
            <TenderNumberSearch />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Што следиме за вас</CardTitle>
            <CardDescription>
              Клучни зборови од насловите на тендерите што сакате да ги добиете.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <KeywordsEditor onSaved={() => void load()} />
          </CardContent>
        </Card>
      </div>

      {loading ? (
        <p className="py-12 text-center text-sm text-muted-foreground">Се вчитува…</p>
      ) : error ? (
        <Card>
          <CardContent className="space-y-3 py-8 text-center text-sm">
            <p className="font-medium text-destructive">Грешка</p>
            <p className="text-muted-foreground">{error}</p>
            <Button variant="outline" onClick={() => void load()}>
              Обиди се повторно
            </Button>
          </CardContent>
        </Card>
      ) : tenders.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-12 text-center">
            <Search className="h-8 w-8 text-muted-foreground" />
            <p className="max-w-md text-sm text-muted-foreground">
              Сè уште немаме тендери што одговараат на вашиот профил. Додајте клучни зборови погоре, внесете
              број на тендер или пишете ни што сакате да добиете.
            </p>
            <Link href="/portal/messages">
              <Button variant="outline">Пишете ни</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {tenders.map((t) => (
            <MatchedTenderCard key={t.tender_id} tender={t} />
          ))}
        </div>
      )}
    </div>
  );
}
