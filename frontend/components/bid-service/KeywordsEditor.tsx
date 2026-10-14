'use client';

import { useEffect, useState } from 'react';
import { Loader2, Plus, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api } from '@/lib/api';

const MAX_KEYWORDS = 20;

interface KeywordsEditorProps {
  /** Called after a successful save, e.g. to reload the matched tenders. */
  onSaved?: (keywords: string[]) => void;
  className?: string;
}

/**
 * Keywords that drive „Тендери за мене“ and the tender alerts. Matching runs on
 * tender titles, so short phrases work best (e.g. „одржување на софтвер“).
 */
export default function KeywordsEditor({ onSaved, className }: KeywordsEditorProps) {
  const [keywords, setKeywords] = useState<string[]>([]);
  const [saved, setSaved] = useState<string[]>([]);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getPortalKeywords()
      .then((res) => {
        if (cancelled) return;
        setKeywords(res.keywords);
        setSaved(res.keywords);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Клучните зборови не се вчитаа.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const add = () => {
    const kw = draft.replace(/\s+/g, ' ').trim();
    setNotice(null);
    if (kw.length < 3) {
      setError('Клучниот збор мора да има најмалку 3 знаци.');
      return;
    }
    if (keywords.some((k) => k.toLowerCase() === kw.toLowerCase())) {
      setDraft('');
      return;
    }
    if (keywords.length >= MAX_KEYWORDS) {
      setError(`Најмногу ${MAX_KEYWORDS} клучни зборови.`);
      return;
    }
    setError(null);
    setKeywords([...keywords, kw.slice(0, 60)]);
    setDraft('');
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const res = await api.setPortalKeywords(keywords);
      setKeywords(res.keywords);
      setSaved(res.keywords);
      setNotice('Зачувано.');
      onSaved?.(res.keywords);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Зачувувањето не успеа.');
    } finally {
      setSaving(false);
    }
  };

  const dirty = keywords.join('\u0000') !== saved.join('\u0000');

  if (loading) {
    return <p className="text-sm text-muted-foreground">Се вчитува…</p>;
  }

  return (
    <div className={className}>
      <div className="flex flex-wrap gap-2">
        {keywords.length === 0 && (
          <p className="text-sm text-muted-foreground">Сè уште немате клучни зборови.</p>
        )}
        {keywords.map((k) => (
          <span
            key={k}
            className="inline-flex items-center gap-1 rounded-full border bg-muted px-3 py-1 text-sm"
          >
            {k}
            <button
              type="button"
              aria-label={`Отстрани ${k}`}
              className="text-muted-foreground hover:text-foreground"
              onClick={() => setKeywords(keywords.filter((x) => x !== k))}
              disabled={saving}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </span>
        ))}
      </div>
      <form
        className="mt-3 flex flex-col gap-2 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          add();
        }}
      >
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="на пр. одржување на софтвер"
          maxLength={60}
          disabled={saving}
        />
        <Button type="submit" variant="outline" disabled={saving || !draft.trim()}>
          <Plus className="mr-1.5 h-4 w-4" />
          Додај
        </Button>
        <Button type="button" onClick={save} disabled={saving || !dirty}>
          {saving && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
          Зачувај
        </Button>
      </form>
      {error && <p className="mt-2 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {notice && <p className="mt-2 text-sm text-green-700 dark:text-green-400">{notice}</p>}
    </div>
  );
}
