'use client';

import { useState } from 'react';
import { Check, Download, FileText, Loader2, PenLine } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { BID_FILE_KIND_LABELS, FILE_APPROVAL_LABELS } from '@/lib/bid-service-types';
import type { BidFile, FileApprovalStatus } from '@/lib/bid-service-types';

interface DeliverablesListProps {
  jobId: string;
  files: BidFile[];
  canReview: boolean;
  onChanged: () => void;
}

const APPROVAL_CLASS: Record<FileApprovalStatus, string> = {
  pending: 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-950/50 dark:text-amber-200 dark:border-amber-800',
  approved: 'bg-green-100 text-green-800 border-green-200 dark:bg-green-950/50 dark:text-green-200 dark:border-green-800',
  changes_requested: 'bg-red-100 text-red-800 border-red-200 dark:bg-red-950/50 dark:text-red-200 dark:border-red-800',
};

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

type Busy = { id: string; action: 'download' | 'approve' | 'changes' } | null;

/** The client's view of the deliverables we prepared, with download and review actions. */
export default function DeliverablesList({ jobId, files, canReview, onChanged }: DeliverablesListProps) {
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState<string | null>(null);
  const [commentFor, setCommentFor] = useState<string | null>(null);
  const [comment, setComment] = useState('');

  const run = async (id: string, action: NonNullable<Busy>['action'], fn: () => Promise<unknown>, reload: boolean) => {
    setBusy({ id, action });
    setError(null);
    try {
      await fn();
      if (reload) onChanged();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Акцијата не успеа. Обидете се повторно.');
      return false;
    } finally {
      setBusy(null);
    }
  };

  if (files.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Документите ќе се појават тука штом ги подготвиме.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      <ul className="divide-y rounded-md border">
        {files.map((f) => {
          const isBusy = busy?.id === f.id;
          const commentOpen = commentFor === f.id;
          return (
            <li key={f.id} className="space-y-2 p-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex min-w-0 items-start gap-2">
                  <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0">
                    <p className="text-xs text-muted-foreground">
                      {BID_FILE_KIND_LABELS[f.kind] ?? f.kind} · {formatBytes(f.size_bytes)}
                    </p>
                    <p className="break-words font-medium">{f.title}</p>
                  </div>
                </div>
                <span
                  className={cn(
                    'inline-flex w-fit shrink-0 items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold',
                    APPROVAL_CLASS[f.approval_status]
                  )}
                >
                  {FILE_APPROVAL_LABELS[f.approval_status]}
                </span>
              </div>

              {f.client_comment && (
                <p className="rounded-md bg-muted px-3 py-2 text-sm">
                  <span className="font-medium">Ваш коментар: </span>
                  <span className="whitespace-pre-wrap">{f.client_comment}</span>
                </p>
              )}

              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={isBusy}
                  onClick={() =>
                    run(f.id, 'download', () => api.downloadBidJobFile(jobId, f.id, f.original_name), false)
                  }
                >
                  {isBusy && busy?.action === 'download' ? (
                    <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="mr-1.5 h-4 w-4" />
                  )}
                  Преземи
                </Button>
                {canReview && f.approval_status !== 'approved' && (
                  <Button
                    size="sm"
                    disabled={isBusy}
                    onClick={() => run(f.id, 'approve', () => api.approveBidFile(jobId, f.id), true)}
                  >
                    {isBusy && busy?.action === 'approve' ? (
                      <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    ) : (
                      <Check className="mr-1.5 h-4 w-4" />
                    )}
                    Одобри
                  </Button>
                )}
                {canReview && !commentOpen && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={isBusy}
                    onClick={() => {
                      setCommentFor(f.id);
                      setComment('');
                    }}
                  >
                    <PenLine className="mr-1.5 h-4 w-4" />
                    Побарај измени
                  </Button>
                )}
              </div>

              {canReview && commentOpen && (
                <div className="space-y-2">
                  <Textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="Опишете кои измени ви се потребни…"
                    rows={3}
                    maxLength={2000}
                    disabled={isBusy}
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      disabled={isBusy || !comment.trim()}
                      onClick={async () => {
                        const ok = await run(
                          f.id,
                          'changes',
                          () => api.requestBidFileChanges(jobId, f.id, comment.trim()),
                          true
                        );
                        if (ok) {
                          setCommentFor(null);
                          setComment('');
                        }
                      }}
                    >
                      {isBusy && busy?.action === 'changes' && (
                        <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                      )}
                      Испрати забелешки
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={isBusy}
                      onClick={() => {
                        setCommentFor(null);
                        setComment('');
                      }}
                    >
                      Откажи
                    </Button>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
