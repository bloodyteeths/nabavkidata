'use client';

import { useCallback, useEffect, useState } from 'react';
import { ExternalLink, Hammer, RefreshCw } from 'lucide-react';
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
import { tenderUrl } from '@/lib/utils';
import {
  OPS_REPLY_CC,
  OPS_VIOLATION_LABELS,
  type OpsShortlist,
  type OpsShortlistPreview,
  type OpsShortlistsResponse,
} from '@/lib/ops-types';

const MIN_PICK = 2;
const MAX_PICK = 4;

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

/** Snap any YYYY-MM-DD to the Monday of its ISO week. */
function toMonday(value: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!m) return value;
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
  const dow = (d.getUTCDay() + 6) % 7; // Monday = 0
  d.setUTCDate(d.getUTCDate() - dow);
  return d.toISOString().slice(0, 10);
}

const STATUS_LABEL: Record<OpsShortlist['status'], string> = {
  draft: 'Нацрт',
  sent: 'Испратена',
  skipped: 'Прескокната',
};

interface CardProps {
  sl: OpsShortlist;
  onChanged: () => Promise<void>;
}

function ShortlistCard({ sl, onChanged }: CardProps) {
  const isDraft = sl.status === 'draft';
  const [subject, setSubject] = useState(sl.subject);
  const [intro, setIntro] = useState(sl.intro_text);
  const [picked, setPicked] = useState<string[]>(sl.items.filter((i) => i.picked).map((i) => i.tender_id));
  const [notes, setNotes] = useState<Record<string, string>>(() => {
    const n: Record<string, string> = {};
    sl.items.forEach((i) => {
      if (i.note) n[i.tender_id] = i.note;
    });
    return n;
  });
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [preview, setPreview] = useState<OpsShortlistPreview | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [violations, setViolations] = useState<string[] | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);

  const togglePick = (tenderId: string, checked: boolean) => {
    setDirty(true);
    setPicked((prev) => {
      if (checked) {
        if (prev.includes(tenderId)) return prev;
        if (prev.length >= MAX_PICK) {
          toast.error(`Најмногу ${MAX_PICK} тендери.`);
          return prev;
        }
        return [...prev, tenderId];
      }
      return prev.filter((t) => t !== tenderId);
    });
  };

  const body = () => {
    const pickedNotes: Record<string, string> = {};
    picked.forEach((t) => {
      const n = (notes[t] || '').trim();
      if (n) pickedNotes[t] = n.slice(0, 300);
    });
    return { subject, intro_text: intro, picked, notes: pickedNotes };
  };

  const save = async (quiet = false): Promise<boolean> => {
    setBusy(true);
    try {
      await api.updateOpsShortlist(sl.id, body());
      setDirty(false);
      if (!quiet) toast.success('Зачувано');
      return true;
    } catch (err) {
      toast.error(errorMessage(err, 'Зачувувањето не успеа.'));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const showPreview = async () => {
    if (isDraft && dirty && !(await save(true))) return;
    setBusy(true);
    try {
      setPreview(await api.previewOpsShortlist(sl.id));
    } catch (err) {
      toast.error(errorMessage(err, 'Прегледот не може да се вчита.'));
    } finally {
      setBusy(false);
    }
  };

  const openSend = async () => {
    if (dirty && !(await save(true))) return;
    setViolations(null);
    setSendError(null);
    setConfirmOpen(true);
  };

  const send = async (force: boolean) => {
    setBusy(true);
    setSendError(null);
    try {
      const res = await api.sendOpsShortlist(sl.id, force);
      toast.success(`Испратено до ${res.to ?? sl.email}`);
      setConfirmOpen(false);
      await onChanged();
    } catch (err) {
      const v = violationsOf(err);
      if (v) setViolations(v);
      else setSendError(errorMessage(err, 'Шортлистата не е испратена.'));
    } finally {
      setBusy(false);
    }
  };

  const skip = async () => {
    setBusy(true);
    try {
      await api.skipOpsShortlist(sl.id);
      toast.success('Прескокната');
      await onChanged();
    } catch (err) {
      toast.error(errorMessage(err, 'Не успеа.'));
    } finally {
      setBusy(false);
    }
  };

  const pickedClosed = picked.some((t) => !sl.items.find((i) => i.tender_id === t)?.open);
  const canSend = isDraft && picked.length >= MIN_PICK && picked.length <= MAX_PICK && !pickedClosed;

  return (
    <Card>
      <CardContent className="space-y-4 p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="font-semibold">{sl.company_name || sl.email}</h3>
            <p className="text-xs text-muted-foreground">
              {sl.email} · {sl.account_type}
              {sl.sent_at && ` · испратена ${formatDay(sl.sent_at)}`}
            </p>
          </div>
          <Badge variant={sl.status === 'sent' ? 'success' : sl.status === 'skipped' ? 'secondary' : 'warning'}>
            {STATUS_LABEL[sl.status]}
          </Badge>
        </div>

        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Избрани {picked.length}/{MAX_PICK} (најмалку {MIN_PICK})
          </p>
          {sl.items.map((it) => {
            const checked = picked.includes(it.tender_id);
            const disabled =
              !isDraft || busy || (!it.open && !checked) || (!checked && picked.length >= MAX_PICK);
            return (
              <div key={it.tender_id} className="rounded-md border p-2 text-sm">
                <label className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={checked}
                    disabled={disabled}
                    onChange={(e) => togglePick(it.tender_id, e.target.checked)}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="font-medium">{it.title}</span>
                    {!it.open && (
                      <Badge variant="destructive" className="ml-2">
                        затворен
                      </Badge>
                    )}
                    <span className="block text-xs text-muted-foreground">
                      {it.procuring_entity || '—'} · рок {formatDay(it.closing_date)}
                      {it.estimated_value_mkd != null &&
                        ` · ${Math.round(it.estimated_value_mkd).toLocaleString('mk-MK')} МКД (интерно)`}
                      {it.reason && ` · ${it.reason}`}
                    </span>
                  </span>
                  <a
                    href={tenderUrl(it.tender_id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600"
                    aria-label="Отвори тендер"
                  >
                    <ExternalLink className="h-4 w-4" />
                  </a>
                </label>
                {checked && (
                  <Input
                    className="mt-2"
                    placeholder="Белешка за клиентот (опционално)"
                    maxLength={300}
                    value={notes[it.tender_id] ?? ''}
                    disabled={!isDraft || busy}
                    onChange={(e) => {
                      setDirty(true);
                      setNotes((n) => ({ ...n, [it.tender_id]: e.target.value }));
                    }}
                  />
                )}
              </div>
            );
          })}
        </div>

        <div className="space-y-2">
          <div>
            <Label htmlFor={`sl-subj-${sl.id}`} className="text-xs">
              Тема
            </Label>
            <Input
              id={`sl-subj-${sl.id}`}
              value={subject}
              maxLength={200}
              disabled={!isDraft || busy}
              onChange={(e) => {
                setDirty(true);
                setSubject(e.target.value);
              }}
            />
          </div>
          <div>
            <Label htmlFor={`sl-intro-${sl.id}`} className="text-xs">
              Вовед
            </Label>
            <Textarea
              id={`sl-intro-${sl.id}`}
              rows={4}
              value={intro}
              disabled={!isDraft || busy}
              onChange={(e) => {
                setDirty(true);
                setIntro(e.target.value);
              }}
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {isDraft && (
            <Button type="button" size="sm" variant="secondary" disabled={busy || !dirty} onClick={() => save()}>
              Зачувај
            </Button>
          )}
          <Button type="button" size="sm" variant="outline" disabled={busy} onClick={showPreview}>
            Преглед
          </Button>
          {isDraft && (
            <>
              <Button type="button" size="sm" disabled={busy || !canSend} onClick={openSend}>
                Испрати
              </Button>
              <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={skip}>
                Прескокни
              </Button>
            </>
          )}
        </div>
      </CardContent>

      <Dialog open={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{preview?.subject}</DialogTitle>
            <DialogDescription>
              До {preview?.to} (cc {OPS_REPLY_CC})
            </DialogDescription>
          </DialogHeader>
          {preview && preview.violations.length > 0 && (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
              <p className="font-medium">Прекршувања на правилата за текст:</p>
              <ul className="ml-4 list-disc">
                {preview.violations.map((v) => (
                  <li key={v}>{OPS_VIOLATION_LABELS[v] ?? v}</li>
                ))}
              </ul>
            </div>
          )}
          <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-md bg-muted/40 p-3 text-xs">
            {preview?.body_text}
          </pre>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmOpen} onOpenChange={(o) => !busy && setConfirmOpen(o)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Испрати шортлиста?</DialogTitle>
            <DialogDescription>
              Ќе се испрати една порака до <strong>{sl.email}</strong> (cc {OPS_REPLY_CC}) со {picked.length}{' '}
              избрани тендери.
            </DialogDescription>
          </DialogHeader>
          {violations && (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
              <p className="font-medium">Текстот ги крши правилата:</p>
              <ul className="ml-4 list-disc">
                {violations.map((v) => (
                  <li key={v}>{OPS_VIOLATION_LABELS[v] ?? v}</li>
                ))}
              </ul>
            </div>
          )}
          {sendError && <p className="text-sm text-red-600">{sendError}</p>}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setConfirmOpen(false)} disabled={busy}>
              Откажи
            </Button>
            {violations ? (
              <Button type="button" variant="destructive" onClick={() => send(true)} disabled={busy}>
                {busy ? 'Се испраќа…' : 'Испрати сепак'}
              </Button>
            ) : (
              <Button type="button" onClick={() => send(false)} disabled={busy}>
                {busy ? 'Се испраќа…' : 'Испрати'}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

export default function AdminShortlistsPage() {
  const [week, setWeek] = useState<string>('');
  // Monday of the current week as the server sees it (first load without ?week).
  const [currentWeek, setCurrentWeek] = useState<string>('');
  const [data, setData] = useState<OpsShortlistsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.listOpsShortlists(week || undefined);
      setData(res);
      if (!week && res.week_start) {
        setWeek(res.week_start);
        setCurrentWeek(res.week_start);
      }
    } catch (err) {
      setError(errorMessage(err, 'Шортлистите не можат да се вчитаат.'));
    } finally {
      setLoading(false);
    }
  }, [week]);

  useEffect(() => {
    load();
  }, [load]);

  const build = async () => {
    setBuilding(true);
    try {
      const res = await api.buildOpsShortlists();
      toast.success(`Изградени ${res.built}, постоечки ${res.existing}, без кандидати ${res.no_candidates}`);
      await load();
    } catch (err) {
      toast.error(errorMessage(err, 'Градењето не успеа.'));
    } finally {
      setBuilding(false);
    }
  };

  const shortlists = data?.shortlists ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Шортлисти</h1>
          <p className="text-sm text-muted-foreground">
            Рачно избрани тендери за клиенти, по недела. Ништо не се испраќа без Ваш клик.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <Label htmlFor="sl-week" className="text-xs">
              Недела (понеделник)
            </Label>
            <Input
              id="sl-week"
              type="date"
              value={week}
              onChange={(e) => e.target.value && setWeek(toMonday(e.target.value))}
            />
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => load()}>
            <RefreshCw className="mr-1 h-4 w-4" /> Освежи
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={build}
            disabled={building || !currentWeek || week !== currentWeek}
            title={
              week !== currentWeek ? 'Градењето е можно само за тековната недела' : 'Изгради за тековната недела'
            }
          >
            <Hammer className="mr-1 h-4 w-4" />{' '}
            {building ? 'Се гради…' : week !== currentWeek ? 'Изгради (само тековна недела)' : 'Изгради сега'}
          </Button>
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {loading && !data && <p className="text-sm text-muted-foreground">Се вчитува…</p>}
      {data && (
        <p className="text-sm text-muted-foreground">
          Недела од {formatDay(data.week_start)} · {shortlists.length} шортлисти
        </p>
      )}
      {data && shortlists.length === 0 && (
        <Card>
          <CardContent className="p-6 text-center text-muted-foreground">Нема шортлисти за оваа недела.</CardContent>
        </Card>
      )}

      {shortlists.map((sl) => (
        <ShortlistCard
          key={`${sl.id}:${sl.status}:${sl.built_at}:${sl.sent_at ?? ''}`}
          sl={sl}
          onChanged={load}
        />
      ))}
    </div>
  );
}
