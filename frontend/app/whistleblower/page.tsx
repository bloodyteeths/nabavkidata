'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Shield, Lock, Send, Copy, CheckCircle2, AlertTriangle,
  Clock, Eye, Plus, Trash2, Loader2, ArrowLeft, FileText,
} from 'lucide-react';

const API_URL = typeof window !== 'undefined'
  ? (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://api.nabavkidata.com')
  : 'https://api.nabavkidata.com';

const CATEGORIES: Record<string, string> = {
  bid_rigging: 'Нелојална конкуренција / Намештени понуди',
  bribery: 'Поткуп / Корупција',
  conflict_of_interest: 'Конфликт на интереси',
  fraud: 'Измама',
  other: 'Друго',
};

const STATUS_LABELS: Record<string, string> = {
  submitted: 'Поднесена',
  under_review: 'Во преглед',
  investigating: 'Се истражува',
  resolved: 'Решена',
  dismissed: 'Одбиена',
  linked: 'Поврзана со истрага',
};

const STATUS_COLORS: Record<string, string> = {
  submitted: 'bg-blue-100 text-blue-800 border-blue-300',
  under_review: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  investigating: 'bg-orange-100 text-orange-800 border-orange-300',
  resolved: 'bg-green-100 text-green-800 border-green-300',
  dismissed: 'bg-gray-100 text-gray-600 border-gray-300',
  linked: 'bg-purple-100 text-purple-800 border-purple-300',
};

type Mode = 'submit' | 'status';

interface StatusResult {
  status: string;
  message: string;
  submitted_at: string;
  last_updated: string;
}

export default function WhistleblowerPage() {
  const [mode, setMode] = useState<Mode>('submit');
  const [category, setCategory] = useState('');
  const [description, setDescription] = useState('');
  const [evidenceUrls, setEvidenceUrls] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [trackingCode, setTrackingCode] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [copied, setCopied] = useState(false);

  // Status mode state
  const [statusCode, setStatusCode] = useState('');
  const [statusResult, setStatusResult] = useState<StatusResult | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [statusError, setStatusError] = useState('');

  const addEvidenceUrl = () => {
    if (evidenceUrls.length < 5) setEvidenceUrls([...evidenceUrls, '']);
  };

  const removeEvidenceUrl = (index: number) => {
    setEvidenceUrls(evidenceUrls.filter((_, i) => i !== index));
  };

  const updateEvidenceUrl = (index: number, value: string) => {
    const updated = [...evidenceUrls];
    updated[index] = value;
    setEvidenceUrls(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (description.length < 20) {
      setError('Описот мора да содржи најмалку 20 карактери.');
      return;
    }
    if (!category) {
      setError('Изберете категорија.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const body: Record<string, unknown> = { description, category };
      const validUrls = evidenceUrls.filter(u => u.trim());
      if (validUrls.length > 0) body.evidence_urls = validUrls;

      const res = await fetch(`${API_URL}/api/whistleblower/tips`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || 'Грешка при поднесување.');
      }

      const data = await res.json();
      setTrackingCode(data.tracking_code);
      setSubmitted(true);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Грешка при поднесување. Обидете се повторно.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleCheckStatus = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!statusCode.trim()) return;

    setStatusLoading(true);
    setStatusError('');
    setStatusResult(null);

    try {
      const res = await fetch(`${API_URL}/api/whistleblower/tips/${statusCode.trim()}/status`);
      if (!res.ok) {
        if (res.status === 404) throw new Error('Пријавата не е пронајдена. Проверете го кодот.');
        throw new Error('Грешка при проверка.');
      }
      const data = await res.json();
      setStatusResult(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Грешка при проверка.';
      setStatusError(message);
    } finally {
      setStatusLoading(false);
    }
  };

  const copyTrackingCode = async () => {
    await navigator.clipboard.writeText(trackingCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const resetForm = () => {
    setCategory('');
    setDescription('');
    setEvidenceUrls([]);
    setError('');
    setTrackingCode('');
    setSubmitted(false);
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString('mk-MK', {
        year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit',
      });
    } catch { return dateStr; }
  };

  // ── Success Screen ──
  if (submitted && trackingCode) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
        <Card className="w-full max-w-lg border-green-700 bg-slate-900 text-slate-100">
          <CardHeader className="text-center pb-2">
            <CheckCircle2 className="mx-auto h-14 w-14 text-green-400 mb-3" />
            <CardTitle className="text-xl text-green-400">Пријавата е успешно поднесена</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="bg-slate-800 rounded-lg p-5 text-center border border-slate-700">
              <p className="text-sm text-slate-400 mb-2">Вашиот код за следење:</p>
              <div className="flex items-center justify-center gap-2">
                <span className="text-2xl font-mono font-bold tracking-wider text-green-300">
                  {trackingCode}
                </span>
                <Button variant="ghost" size="sm" onClick={copyTrackingCode} className="text-slate-400 hover:text-white">
                  {copied ? <CheckCircle2 className="h-4 w-4 text-green-400" /> : <Copy className="h-4 w-4" />}
                </Button>
              </div>
            </div>

            <div className="bg-yellow-950/40 border border-yellow-700/50 rounded-lg p-4 flex gap-3">
              <AlertTriangle className="h-5 w-5 text-yellow-500 shrink-0 mt-0.5" />
              <div className="text-sm text-yellow-200">
                <p className="font-semibold mb-1">ЗАЧУВАЈТЕ ГО ОВОЈ КОД!</p>
                <p className="text-yellow-300/80">
                  Ова е единствениот начин да го проверите статусот на вашата пријава. Не можеме да го
                  повратиме кодот бидејќи не собираме лични податоци.
                </p>
              </div>
            </div>

            <div className="flex flex-col gap-2 pt-2">
              <Button onClick={() => { setMode('status'); setStatusCode(trackingCode); setSubmitted(false); }}
                className="w-full bg-slate-700 hover:bg-slate-600">
                <Eye className="mr-2 h-4 w-4" /> Проверете статус
              </Button>
              <Button variant="outline" onClick={resetForm}
                className="w-full border-slate-600 text-slate-300 hover:bg-slate-800">
                <FileText className="mr-2 h-4 w-4" /> Поднесете нова пријава
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── Main Layout ──
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="max-w-2xl mx-auto px-4 py-10">
        {/* Mode Tabs */}
        <div className="flex gap-2 mb-8">
          <Button variant={mode === 'submit' ? 'default' : 'outline'} size="sm"
            onClick={() => setMode('submit')}
            className={mode === 'submit' ? 'bg-slate-700' : 'border-slate-600 text-slate-400 hover:bg-slate-800'}>
            <Send className="mr-2 h-4 w-4" /> Пријавете
          </Button>
          <Button variant={mode === 'status' ? 'default' : 'outline'} size="sm"
            onClick={() => setMode('status')}
            className={mode === 'status' ? 'bg-slate-700' : 'border-slate-600 text-slate-400 hover:bg-slate-800'}>
            <Eye className="mr-2 h-4 w-4" /> Проверете статус
          </Button>
        </div>

        {mode === 'submit' ? (
          <>
            {/* Header */}
            <div className="text-center mb-8">
              <Shield className="mx-auto h-12 w-12 text-blue-400 mb-4" />
              <h1 className="text-2xl font-bold mb-2">Анонимно пријавување на корупција</h1>
              <p className="text-slate-400 text-sm max-w-md mx-auto">
                Вашиот идентитет е целосно заштитен. Не собираме IP адреси или лични податоци.
              </p>
            </div>

            {/* Privacy Notice */}
            <Card className="mb-6 border-blue-800/50 bg-blue-950/30">
              <CardContent className="pt-4 pb-4">
                <div className="flex gap-3">
                  <Lock className="h-5 w-5 text-blue-400 shrink-0 mt-0.5" />
                  <div className="text-sm text-blue-200/80 space-y-1">
                    <p>Не е потребна регистрација или најава.</p>
                    <p>Не собираме IP адреси, cookies или лични податоци.</p>
                    <p>По поднесувањето ќе добиете код за следење - единствен начин за проверка на статусот.</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Категорија <span className="text-red-400">*</span>
                </label>
                <Select value={category} onValueChange={setCategory}>
                  <SelectTrigger className="bg-slate-900 border-slate-700 text-slate-100">
                    <SelectValue placeholder="Изберете категорија" />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-900 border-slate-700">
                    {Object.entries(CATEGORIES).map(([value, label]) => (
                      <SelectItem key={value} value={value} className="text-slate-100 focus:bg-slate-800">
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Опис <span className="text-red-400">*</span>
                </label>
                <Textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Опишете ја ситуацијата детално. Вклучете имиња на институции, компании, броеви на тендери, датуми и суми доколку ги знаете."
                  rows={6}
                  maxLength={50000}
                  className="bg-slate-900 border-slate-700 text-slate-100 placeholder:text-slate-500 resize-y"
                />
                <div className="flex justify-between mt-1 text-xs text-slate-500">
                  <span>{description.length < 20 ? `Минимум 20 карактери` : ''}</span>
                  <span>{description.length.toLocaleString()} / 50,000</span>
                </div>
              </div>

              {/* Evidence URLs */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Линкови до докази <span className="text-slate-500">(опционално)</span>
                </label>
                <div className="space-y-2">
                  {evidenceUrls.map((url, i) => (
                    <div key={i} className="flex gap-2">
                      <Input
                        value={url}
                        onChange={(e) => updateEvidenceUrl(i, e.target.value)}
                        placeholder="https://..."
                        type="url"
                        className="bg-slate-900 border-slate-700 text-slate-100 placeholder:text-slate-500"
                      />
                      <Button type="button" variant="ghost" size="icon" onClick={() => removeEvidenceUrl(i)}
                        className="text-slate-400 hover:text-red-400 shrink-0">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
                {evidenceUrls.length < 5 && (
                  <Button type="button" variant="ghost" size="sm" onClick={addEvidenceUrl}
                    className="mt-2 text-slate-400 hover:text-slate-200">
                    <Plus className="mr-1 h-4 w-4" /> Додај линк
                  </Button>
                )}
              </div>

              {error && (
                <div className="bg-red-950/40 border border-red-700/50 rounded-lg p-3 text-sm text-red-300 flex gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" /> {error}
                </div>
              )}

              <Button type="submit" disabled={loading || !category || description.length < 20}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-40">
                {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                {loading ? 'Се поднесува...' : 'Поднеси пријава'}
              </Button>
            </form>
          </>
        ) : (
          <>
            {/* Status Check Mode */}
            <div className="text-center mb-8">
              <Eye className="mx-auto h-12 w-12 text-slate-400 mb-4" />
              <h1 className="text-2xl font-bold mb-2">Проверете го статусот на вашата пријава</h1>
              <p className="text-slate-400 text-sm">
                Внесете го кодот за следење што го добивте при поднесувањето.
              </p>
            </div>

            <form onSubmit={handleCheckStatus} className="space-y-4 mb-6">
              <Input
                value={statusCode}
                onChange={(e) => setStatusCode(e.target.value.toUpperCase())}
                placeholder="WB-XXXX-YYYY"
                className="bg-slate-900 border-slate-700 text-slate-100 text-center font-mono text-lg tracking-wider placeholder:text-slate-600"
              />
              <Button type="submit" disabled={statusLoading || !statusCode.trim()}
                className="w-full bg-slate-700 hover:bg-slate-600 disabled:opacity-40">
                {statusLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Eye className="mr-2 h-4 w-4" />}
                {statusLoading ? 'Се проверува...' : 'Провери'}
              </Button>
            </form>

            {statusError && (
              <div className="bg-red-950/40 border border-red-700/50 rounded-lg p-3 text-sm text-red-300 flex gap-2 mb-4">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" /> {statusError}
              </div>
            )}

            {statusResult && (
              <Card className="border-slate-700 bg-slate-900">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base text-slate-300">Статус на пријавата</CardTitle>
                    <Badge className={`${STATUS_COLORS[statusResult.status] || STATUS_COLORS.submitted} border`}>
                      {STATUS_LABELS[statusResult.status] || statusResult.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {statusResult.message && (
                    <p className="text-sm text-slate-300">{statusResult.message}</p>
                  )}
                  <div className="grid grid-cols-2 gap-3 text-xs text-slate-400">
                    <div className="flex items-center gap-1.5">
                      <Clock className="h-3.5 w-3.5" />
                      <div>
                        <p className="text-slate-500">Поднесена</p>
                        <p>{formatDate(statusResult.submitted_at)}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Clock className="h-3.5 w-3.5" />
                      <div>
                        <p className="text-slate-500">Последна промена</p>
                        <p>{formatDate(statusResult.last_updated)}</p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            <Button variant="ghost" size="sm" onClick={() => setMode('submit')}
              className="mt-6 text-slate-500 hover:text-slate-300">
              <ArrowLeft className="mr-1 h-4 w-4" /> Назад кон пријавување
            </Button>
          </>
        )}

        {/* Footer */}
        <div className="mt-12 text-center text-xs text-slate-600">
          <Lock className="inline h-3 w-3 mr-1" />
          Заштитена платформа - NabavkiData.com
        </div>
      </div>
    </div>
  );
}
