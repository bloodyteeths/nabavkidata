"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { RefreshCcw, Trash2, Save } from "lucide-react";
import { toast } from "sonner";

type SavedSearch = { id: string; name: string; filters: Record<string, any>; created_at: string };

export default function SavedSearchesPage() {
  const [items, setItems] = useState<SavedSearch[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [filters, setFilters] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getSavedSearches();
      setItems(result.items || []);
    } catch (err) {
      console.error("Failed to load saved searches:", err);
      setError("Не може да ги вчитаме зачуваните пребарувања.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    if (!name.trim()) {
      toast.error("Името е задолжително.");
      return;
    }
    let parsedFilters: Record<string, any> = {};
    if (filters.trim()) {
      try {
        parsedFilters = JSON.parse(filters);
      } catch (e) {
        toast.error("Filters мора да биде валиден JSON.");
        return;
      }
    }
    try {
      setSaving(true);
      await api.createSavedSearch({ name, filters: parsedFilters });
      setName("");
      setFilters("");
      await load();
      toast.success("Пребарувањето е зачувано.");
    } catch (err) {
      console.error("Failed to create saved search:", err);
      toast.error("Не успеавме да зачуваме пребарување.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.deleteSavedSearch(id);
      setItems((prev) => prev.filter((i) => i.id !== id));
      toast.success("Избришано.");
    } catch (err) {
      console.error("Failed to delete saved search:", err);
      toast.error("Бришењето не успеа.");
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Зачувани пребарувања</h1>
          <p className="text-sm text-muted-foreground">Креирај и управувај со зачуваните пребарувања (backend API).</p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCcw className="h-4 w-4 mr-2" />
          Освежи
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Ново пребарување</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input placeholder="Име" value={name} onChange={(e) => setName(e.target.value)} />
          <Textarea
            placeholder='{"search": "градежни", "status": "open"}'
            value={filters}
            onChange={(e) => setFilters(e.target.value)}
            rows={4}
          />
          <div className="flex justify-end">
            <Button onClick={handleCreate} disabled={saving}>
              <Save className="h-4 w-4 mr-2" />
              Зачувај
            </Button>
          </div>
        </CardContent>
      </Card>

      {loading && <p className="text-sm text-muted-foreground">Се вчитуваат зачуваните пребарувања...</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}

      {!loading && !error && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.length === 0 ? (
            <p className="text-sm text-muted-foreground">Нема зачувани пребарувања.</p>
          ) : (
            items.map((item) => (
              <Card key={item.id}>
                <CardHeader className="flex items-start justify-between space-y-0">
                  <div>
                    <CardTitle className="text-base">{item.name}</CardTitle>
                    <p className="text-xs text-muted-foreground">{new Date(item.created_at).toLocaleString()}</p>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => handleDelete(item.id)}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </CardHeader>
                <CardContent>
                  <pre className="text-xs whitespace-pre-wrap bg-muted rounded p-2">
                    {JSON.stringify(item.filters, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}
    </div>
  );
}
