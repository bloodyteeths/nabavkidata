'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Download, FileText, Pencil, Trash2, Upload, X } from 'lucide-react';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api';
import {
  BID_FILE_ACCEPT,
  BID_FILE_MAX_BYTES,
  CLIENT_DOCUMENT_CATEGORIES,
  CLIENT_DOCUMENT_CATEGORY_LABELS,
  type ClientDocument,
  type ClientDocumentCategory,
} from '@/lib/bid-service-types';

const SELECT_CLASS =
  'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50';

function errMsg(e: unknown, fallback: string): string {
  return e instanceof Error && e.message ? e.message : fallback;
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const [y, m, d] = iso.slice(0, 10).split('-');
  return y && m && d ? `${d}.${m}.${y}` : iso;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface EditState {
  title: string;
  category: ClientDocumentCategory;
  expires_on: string;
}

export default function PortalDocumentsPage() {
  const [documents, setDocuments] = useState<ClientDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // upload form
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState<ClientDocumentCategory>('tekovna_sostojba');
  const [title, setTitle] = useState('');
  const [expiresOn, setExpiresOn] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // per-row actions
  const [editingId, setEditingId] = useState<string | null>(null);
  const [edit, setEdit] = useState<EditState | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.getClientDocuments();
      setDocuments(res.documents);
      setLoadError(null);
    } catch (e: unknown) {
      setLoadError(errMsg(e, 'Грешка при вчитување на документите.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const grouped = useMemo(() => {
    return CLIENT_DOCUMENT_CATEGORIES.map((cat) => ({
      category: cat,
      docs: documents.filter((d) => d.category === cat),
    })).filter((g) => g.docs.length > 0);
  }, [documents]);

  const onFileChange = (f: File | null) => {
    setUploadError(null);
    if (f && f.size > BID_FILE_MAX_BYTES) {
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      setUploadError('Датотеката е поголема од 25 MB.');
      return;
    }
    setFile(f);
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setUploadError('Изберете датотека.');
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      await api.uploadClientDocument(file, category, title.trim() || undefined, expiresOn || null);
      toast.success('Документот е прикачен.');
      setFile(null);
      setTitle('');
      setExpiresOn('');
      if (fileInputRef.current) fileInputRef.current.value = '';
      await load();
    } catch (e: unknown) {
      setUploadError(errMsg(e, 'Прикачувањето не успеа.'));
    } finally {
      setUploading(false);
    }
  };

  const startEdit = (doc: ClientDocument) => {
    setEditingId(doc.id);
    setEdit({ title: doc.title, category: doc.category, expires_on: doc.expires_on ?? '' });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEdit(null);
  };

  const saveEdit = async (doc: ClientDocument) => {
    if (!edit) return;
    const newTitle = edit.title.trim();
    if (!newTitle) {
      toast.error('Насловот е задолжителен.');
      return;
    }
    setBusyId(doc.id);
    try {
      await api.updateClientDocument(doc.id, {
        title: newTitle,
        category: edit.category,
        expires_on: edit.expires_on || null,
      });
      toast.success('Промените се зачувани.');
      cancelEdit();
      await load();
    } catch (e: unknown) {
      toast.error(errMsg(e, 'Зачувувањето не успеа.'));
    } finally {
      setBusyId(null);
    }
  };

  const handleDownload = async (doc: ClientDocument) => {
    setBusyId(doc.id);
    try {
      await api.downloadClientDocument(doc.id, doc.original_name);
    } catch (e: unknown) {
      toast.error(errMsg(e, 'Преземањето не успеа.'));
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (doc: ClientDocument) => {
    if (!window.confirm(`Да се избрише документот „${doc.title}“?`)) return;
    setBusyId(doc.id);
    try {
      await api.deleteClientDocument(doc.id);
      toast.success('Документот е избришан.');
      if (editingId === doc.id) cancelEdit();
      await load();
    } catch (e: unknown) {
      toast.error(errMsg(e, 'Бришењето не успеа.'));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-6">
      <div>
        <h1 className="text-2xl font-bold">Документи на компанијата</h1>
        <p className="text-sm text-muted-foreground">
          Документите ги прикачувате еднаш, а ние ги користиме за секоја понуда. Тендерската документација ја
          преземаме ние од е-набавки.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Прикачи документ</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleUpload} className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="doc-file">Датотека</Label>
              <Input
                id="doc-file"
                ref={fileInputRef}
                type="file"
                accept={BID_FILE_ACCEPT}
                disabled={uploading}
                onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
              />
              <p className="text-xs text-muted-foreground">
                PDF, DOC, DOCX, XLS, XLSX, ZIP, JPG, PNG, P7S или XML, најмногу 25 MB.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="doc-category">Категорија</Label>
              <select
                id="doc-category"
                className={SELECT_CLASS}
                value={category}
                disabled={uploading}
                onChange={(e) => setCategory(e.target.value as ClientDocumentCategory)}
              >
                {CLIENT_DOCUMENT_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {CLIENT_DOCUMENT_CATEGORY_LABELS[c]}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="doc-expires">Важи до (опционално)</Label>
              <Input
                id="doc-expires"
                type="date"
                value={expiresOn}
                disabled={uploading}
                onChange={(e) => setExpiresOn(e.target.value)}
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="doc-title">Наслов (опционално)</Label>
              <Input
                id="doc-title"
                value={title}
                maxLength={300}
                disabled={uploading}
                placeholder="Ако го оставите празно, се користи името на датотеката"
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            {uploadError && <p className="text-sm text-destructive md:col-span-2">{uploadError}</p>}
            <div className="md:col-span-2">
              <Button type="submit" disabled={uploading || !file}>
                <Upload className="mr-2 h-4 w-4" />
                {uploading ? 'Се прикачува…' : 'Прикачи'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {loading ? (
        <p className="py-12 text-center text-sm text-muted-foreground">Се вчитува…</p>
      ) : loadError ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-destructive">{loadError}</CardContent>
        </Card>
      ) : grouped.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <FileText className="h-8 w-8 text-muted-foreground" />
            <p className="max-w-md text-sm text-muted-foreground">
              Сè уште немате прикачено документи. Започнете со тековна состојба и даночно уверение.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {grouped.map((group) => (
            <Card key={group.category}>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{CLIENT_DOCUMENT_CATEGORY_LABELS[group.category]}</CardTitle>
              </CardHeader>
              <CardContent className="divide-y p-0">
                {group.docs.map((doc) => {
                  const busy = busyId === doc.id;
                  const isEditing = editingId === doc.id && edit !== null;
                  return (
                    <div key={doc.id} className="px-6 py-4">
                      {isEditing && edit ? (
                        <div className="grid gap-3 md:grid-cols-3">
                          <div className="space-y-1 md:col-span-3">
                            <Label htmlFor={`title-${doc.id}`}>Наслов</Label>
                            <Input
                              id={`title-${doc.id}`}
                              value={edit.title}
                              maxLength={300}
                              disabled={busy}
                              onChange={(e) => setEdit({ ...edit, title: e.target.value })}
                            />
                          </div>
                          <div className="space-y-1">
                            <Label htmlFor={`cat-${doc.id}`}>Категорија</Label>
                            <select
                              id={`cat-${doc.id}`}
                              className={SELECT_CLASS}
                              value={edit.category}
                              disabled={busy}
                              onChange={(e) =>
                                setEdit({ ...edit, category: e.target.value as ClientDocumentCategory })
                              }
                            >
                              {CLIENT_DOCUMENT_CATEGORIES.map((c) => (
                                <option key={c} value={c}>
                                  {CLIENT_DOCUMENT_CATEGORY_LABELS[c]}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="space-y-1">
                            <Label htmlFor={`exp-${doc.id}`}>Важи до</Label>
                            <Input
                              id={`exp-${doc.id}`}
                              type="date"
                              value={edit.expires_on}
                              disabled={busy}
                              onChange={(e) => setEdit({ ...edit, expires_on: e.target.value })}
                            />
                          </div>
                          <div className="flex items-end gap-2">
                            <Button size="sm" disabled={busy} onClick={() => saveEdit(doc)}>
                              {busy ? 'Се зачувува…' : 'Зачувај'}
                            </Button>
                            <Button size="sm" variant="outline" disabled={busy} onClick={cancelEdit}>
                              <X className="mr-1 h-4 w-4" />
                              Откажи
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                          <div className="min-w-0 space-y-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-medium">{doc.title}</span>
                              {doc.expired && (
                                <span className="rounded-full border border-red-200 bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
                                  Истечен
                                </span>
                              )}
                              {!doc.expired && doc.expires_soon && (
                                <span className="rounded-full border border-amber-200 bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
                                  Истекува наскоро
                                </span>
                              )}
                            </div>
                            <p className="truncate text-xs text-muted-foreground">
                              {doc.original_name} · {formatSize(doc.size_bytes)} · прикачено{' '}
                              {formatDate(doc.created_at)}
                              {doc.expires_on ? ` · важи до ${formatDate(doc.expires_on)}` : ''}
                              {doc.uploaded_by_role === 'admin' ? ' · прикачено од нашиот тим' : ''}
                            </p>
                          </div>
                          <div className="flex shrink-0 gap-2">
                            <Button size="sm" variant="outline" disabled={busy} onClick={() => handleDownload(doc)}>
                              <Download className="mr-1 h-4 w-4" />
                              Преземи
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={busy}
                              onClick={() => startEdit(doc)}
                              aria-label="Измени"
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={busy}
                              onClick={() => handleDelete(doc)}
                              aria-label="Избриши"
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
