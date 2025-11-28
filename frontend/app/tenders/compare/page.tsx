"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { RefreshCcw } from "lucide-react";

export default function TenderComparePage() {
  const [idsInput, setIdsInput] = useState("");
  const [data, setData] = useState<Array<any>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tenderIds = idsInput
    .split(/\s|,/)
    .map((id) => id.trim())
    .filter(Boolean);

  async function handleCompare() {
    if (tenderIds.length === 0) {
      setError("Внеси најмалку еден тендер ID (формат: 12345/2025).");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const result = await api.compareTenders(tenderIds);
      setData(result.items || []);
    } catch (err) {
      console.error("Failed to compare tenders:", err);
      setError("Не успеавме да ги споредиме тендерите.");
      setData([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">Споредба на тендери</h1>
          <p className="text-sm text-muted-foreground">Внеси тендер IDs и погледни ги клучните разлики.</p>
        </div>
        <Button size="sm" variant="outline" onClick={handleCompare} disabled={loading}>
          <RefreshCcw className="h-4 w-4 mr-2" />
          Освежи
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Внеси тендер IDs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            placeholder="Пример: 12345/2025, 6789/2024"
            value={idsInput}
            onChange={(e) => setIdsInput(e.target.value)}
          />
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">Оддели со запирка или нов ред.</p>
            <Button onClick={handleCompare} disabled={loading}>
              Спореди
            </Button>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {loading && <p className="text-sm text-muted-foreground">Се вчитуваат резултатите...</p>}

      {!loading && data.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data.map((item, idx) => (
            <Card key={idx}>
              <CardHeader>
                <CardTitle>{item.title || item.tender_id || "Тендер"}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <InfoRow label="ID" value={item.tender_id} />
                <InfoRow label="Институција" value={item.procuring_entity} />
                <InfoRow label="Статус" value={item.status} />
                <InfoRow label="Проценета" value={formatNumber(item.estimated_value_mkd)} />
                <InfoRow label="Доделена" value={formatNumber(item.awarded_value_mkd || item.actual_value_mkd)} />
                <InfoRow label="CPV" value={item.cpv_code} />
                <InfoRow label="Рок" value={item.closing_date} />
                <InfoRow label="Победник" value={item.winner} />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: any }) {
  if (!value && value !== 0) return null;
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-right">{typeof value === "number" ? formatNumber(value) : String(value)}</span>
    </div>
  );
}

function formatNumber(val?: number) {
  if (val === null || val === undefined) return "-";
  return val.toLocaleString("mk-MK");
}
