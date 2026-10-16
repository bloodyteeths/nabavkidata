'use client';

import { useCallback, useEffect, useState } from 'react';
import { CalendarDays, ChevronDown, ChevronRight, ExternalLink, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { api } from '@/lib/api';
import {
  OPS_GROUP_LABELS,
  OPS_GROUP_ORDER,
  OPS_REPLY_CC,
  OPS_VIOLATION_LABELS,
  type OpsFocusItem,
  type OpsFocusResponse,
} from '@/lib/ops-types';

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

function violationsOf(err: unknown): string[] | null {
  const e = err as { status?: number; detail?: unknown } | null;
  if (!e || e.status !== 422) return null;
  const d = e.detail as { violations?: unknown } | null | undefined;
  if (d && typeof d === 'object' && Array.isArray(d.violations)) {
    return d.violations.map((v) => String(v));
  }
  return null;
}

function formatDay(value: string | null | undefined): string {
  if (!value) return '—';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return m ? `${m[3]}.${m[2]}.${m[1]}` : value;
}

function formatMkd(value: number | null | undefined): string | null {
  if (value == null) return null;
  return `${Math.round(value).toLocaleString('mk-MK')} МКД`;
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function mailtoHref(to: string, subject: string, body: string): string {
  return (
    `mailto:${encodeURIComponent(to)}?cc=${encodeURIComponent(OPS_REPLY_CC)}` +
    `&subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
  );
}

function gmailHref(to: string, subject: string, body: string): string {
  return (
    `https://mail.google.com/mail/?view=cm&to=${encodeURIComponent(to)}` +
    `&cc=${encodeURIComponent(OPS_REPLY_CC)}&su=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
  );
}

interface CardProps {
  item: OpsFocusItem;
  busy: boolean;
  onRun: (label: string, fn: () => Promise<unknown>) => Promise<boolean>;
}

function FocusCard({ item, busy, onRun }: CardProps) {
  const [subject, setSubject] = useState(item.draft?.subject ?? '');
  const [body, setBody] = useState(item.draft?.body_text ?? '');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [violations, setViolations] = useState<string[] | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);

  const draft = item.draft;
  const watchId = typeof item.meta?.watch_id === 'string' ? (item.meta.watch_id as string) : null;
  const collapsed = Array.isArray(item.meta?.collapsed_keys) ? (item.meta.collapsed_keys as unknown[]) : [];

  const openConfirm = () => {
    setViolations(null);
    setSendError(null);
    setConfirmOpen(true);
  };

  const send = async (force: boolean) => {
    if (!draft) return;
    setSending(true);
    setSendError(null);
    try {
      const res = await api.sendOpsDraft(item.key, { subject, body_text: body, force });
      toast.success(`Испратено до ${res.to}`);
      setConfirmOpen(false);
      await onRun('', async () => undefined);
    } catch (err) {
      const v = violationsOf(err);
      if (v) {
        setViolations(v);
      } else {
        setSendError(errorMessage(err, 'Пораката не е испратена.'));
      }
    } finally {
      setSending(false);
    }
  };

  const copy = async () => {
    const ok = await copyText(`Тема: ${subject}\n\n${body}`);
    if (ok) toast.success('Копирано');
    else toast.error('Копирањето не успеа');
  };

  return (
    <Card
      id={item.key}
      className={
        item.kind === 'hot_signal' ? 'scroll-mt-20 border-red-300 dark:border-red-800' : 'scroll-mt-20'
      }
    >
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              {item.kind === 'hot_signal' && (
                <Badge className="border-transparent bg-red-600 text-white hover:bg-red-600">ВРЕДНО</Badge>
              )}
              <h3 className="font-semibold leading-snug">{item.title}</h3>
            </div>
            {item.detail && (
              <p className="mt-1 whitespace-pre-line text-sm text-muted-foreground">{item.detail}</p>
            )}
            {item.email && <p className="mt-1 text-xs text-muted-foreground">{item.email}</p>}
          </div>
          <span className="text-xs text-muted-foreground">{formatDay(item.date)}</span>
        </div>

        {item.tender && (
          <div className="rounded-md bg-muted/40 p-2 text-sm">
            <span className="font-medium">{item.tender.tender_id}</span> · {item.tender.title}
            <div className="text-xs text-muted-foreground">
              {item.tender.procuring_entity || '—'} · рок {formatDay(item.tender.closing_date)}
              {formatMkd(item.tender.estimated_value_mkd) && ` · ${formatMkd(item.tender.estimated_value_mkd)} (интерно)`}
            </div>
          </div>
        )}

        {item.links.length > 0 && (
          <div className="flex flex-wrap gap-3 text-sm">
            {item.links.map((l) => (
              <a
                key={l.href + l.label}
                href={l.href}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-blue-600 hover:underline"
              >
                {l.label || 'Отвори'} <ExternalLink className="h-3 w-3" />
              </a>
            ))}
          </div>
        )}

        {collapsed.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Споени ставки за истиот примач: {collapsed.map(String).join(', ')}
          </p>
        )}

        {draft && (
          <div className="space-y-2 rounded-md border p-3">
            <p className="text-xs text-muted-foreground">
              Нацрт до <span className="font-medium text-foreground">{draft.to}</span> (cc {OPS_REPLY_CC})
            </p>
            <div>
              <Label htmlFor={`subj-${item.key}`} className="text-xs">
                Тема
              </Label>
              <Input
                id={`subj-${item.key}`}
                value={subject}
                maxLength={200}
                onChange={(e) => setSubject(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor={`body-${item.key}`} className="text-xs">
                Порака
              </Label>
              <Textarea
                id={`body-${item.key}`}
                rows={10}
                maxLength={8000}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" variant="outline" onClick={copy}>
                Копирај
              </Button>
              <Button type="button" size="sm" variant="outline" asChild>
                <a href={mailtoHref(draft.to, subject, body)}>Mailto</a>
              </Button>
              <Button type="button" size="sm" variant="outline" asChild>
                <a href={gmailHref(draft.to, subject, body)} target="_blank" rel="noopener noreferrer">
                  Gmail
                </a>
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={busy}
                title="Пораката ја испративте од Gmail/пошта: се бележи како испратена до примачот"
                onClick={() =>
                  onRun('Означено како испратено рачно', () =>
                    api.markOpsFocusDone(item.key, { sentManually: true })
                  )
                }
              >
                Испратив рачно
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={openConfirm}
                disabled={busy || !subject.trim() || !body.trim()}
              >
                Испрати
              </Button>
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={busy}
            onClick={() => onRun('Означено како готово', () => api.markOpsFocusDone(item.key))}
          >
            Готово
          </Button>
          <span className="text-xs text-muted-foreground">Одложи:</span>
          {[1, 3, 7].map((d) => (
            <Button
              key={d}
              type="button"
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => onRun(`Одложено ${d} ден${d === 1 ? '' : 'а'}`, () => api.snoozeOpsFocus(item.key, d))}
            >
              {d}д
            </Button>
          ))}
          {item.kind === 'goback' && watchId && (
            <>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() => {
                  if (!window.confirm('Лицето одговорило? Го-бек следењето за ова лице ќе запре.')) return;
                  onRun('Следењето е запрено (одговорија)', () => api.stopOpsWatch(watchId, 'replied'));
                }}
              >
                Одговорија
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() => {
                  if (!window.confirm('Трајно да се запре го-бек следењето (не е заинтересиран)?')) return;
                  onRun('Следењето е запрено (не е заинтересиран)', () =>
                    api.stopOpsWatch(watchId, 'not_interested')
                  );
                }}
              >
                Стоп: не е заинтересиран
              </Button>
            </>
          )}
        </div>
      </CardContent>

      {draft && (
        <Dialog open={confirmOpen} onOpenChange={(o) => !sending && setConfirmOpen(o)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Испрати порака?</DialogTitle>
              <DialogDescription>
                Ќе се испрати една порака до <strong>{draft.to}</strong> (cc {OPS_REPLY_CC}) со тема „{subject}“.
              </DialogDescription>
            </DialogHeader>
            {violations && (
              <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
                <p className="font-medium">Нацртот ги крши правилата за текст:</p>
                <ul className="ml-4 list-disc">
                  {violations.map((v) => (
                    <li key={v}>{OPS_VIOLATION_LABELS[v] ?? v}</li>
                  ))}
                </ul>
              </div>
            )}
            {sendError && <p className="text-sm text-red-600">{sendError}</p>}
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setConfirmOpen(false)} disabled={sending}>
                Откажи
              </Button>
              {violations ? (
                <Button type="button" variant="destructive" onClick={() => send(true)} disabled={sending}>
                  {sending ? 'Се испраќа…' : 'Испрати сепак'}
                </Button>
              ) : (
                <Button type="button" onClick={() => send(false)} disabled={sending}>
                  {sending ? 'Се испраќа…' : 'Испрати'}
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </Card>
  );
}

export default function AdminFocusPage() {
  const [data, setData] = useState<OpsFocusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showDone, setShowDone] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.getOpsFocus(true);
      setData(res);
    } catch (err) {
      setError(errorMessage(err, 'Фокус листата не може да се вчита.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // /admin/focus#<key> (links in the 06:30 email): scroll to that card once loaded.
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    if (!data || scrolled) return;
    setScrolled(true);
    const hash = typeof window !== 'undefined' ? window.location.hash.slice(1) : '';
    if (!hash) return;
    let key = hash;
    try {
      key = decodeURIComponent(hash);
    } catch {
      // keep the raw hash
    }
    document.getElementById(key)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [data, scrolled]);

  const run = useCallback(
    async (label: string, fn: () => Promise<unknown>): Promise<boolean> => {
      setBusy(true);
      try {
        await fn();
        if (label) toast.success(label);
        return true;
      } catch (err) {
        toast.error(errorMessage(err, 'Акцијата не успеа.'));
        return false;
      } finally {
        setBusy(false);
        await load();
      }
    },
    [load]
  );

  const copyCalendar = async () => {
    try {
      const res = await api.getOpsCalendarUrl();
      const ok = await copyText(res.webcal_url);
      if (ok) toast.success('Webcal линкот е копиран');
      else toast.message(res.webcal_url);
    } catch (err) {
      toast.error(errorMessage(err, 'Календарскиот линк не може да се добие.'));
    }
  };

  const items = data?.items ?? [];
  const done = data?.done ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Фокус денес</h1>
          <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
            <span>{data ? formatDay(data.date) : '—'}</span>
            {data?.off_day && <Badge variant="secondary">Неработен ден</Badge>}
            {data && <span>· {data.counts.total} ставки</span>}
          </div>
        </div>
        <div className="flex gap-2">
          <Button type="button" variant="outline" size="sm" onClick={copyCalendar}>
            <CalendarDays className="mr-1 h-4 w-4" /> Календар (.ics)
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={() => load()} disabled={busy}>
            <RefreshCw className="mr-1 h-4 w-4" /> Освежи
          </Button>
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {loading && !data && <p className="text-sm text-muted-foreground">Се вчитува…</p>}

      {data && items.length === 0 && (
        <Card>
          <CardContent className="p-6 text-center text-muted-foreground">Нема отворени ставки за денес.</CardContent>
        </Card>
      )}

      {OPS_GROUP_ORDER.map((group) => {
        const groupItems = items.filter((i) => i.group === group);
        if (groupItems.length === 0) return null;
        return (
          <section key={group} className="space-y-3">
            <h2 className="text-lg font-semibold">
              {OPS_GROUP_LABELS[group]}{' '}
              <span className="text-sm font-normal text-muted-foreground">({groupItems.length})</span>
            </h2>
            {groupItems.map((item) => (
              <FocusCard key={item.key} item={item} busy={busy} onRun={run} />
            ))}
          </section>
        );
      })}

      {data && data.notes.length > 0 && (
        <div className="rounded-md bg-muted/50 p-3 text-sm text-muted-foreground">
          {data.notes.map((n, i) => (
            <p key={i}>{n}</p>
          ))}
        </div>
      )}

      {done.length > 0 && (
        <section className="space-y-2">
          <button
            type="button"
            className="flex items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
            onClick={() => setShowDone((s) => !s)}
          >
            {showDone ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            Завршени денес ({done.length})
          </button>
          {showDone &&
            done.map((item) => (
              <div
                key={item.key}
                className="flex items-center justify-between gap-2 rounded-md border p-2 text-sm text-muted-foreground"
              >
                <span className="min-w-0 flex-1 truncate line-through">{item.title}</span>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={busy}
                  onClick={() => run('Ставката е вратена', () => api.reopenOpsFocus(item.key))}
                >
                  Врати
                </Button>
              </div>
            ))}
        </section>
      )}
    </div>
  );
}
