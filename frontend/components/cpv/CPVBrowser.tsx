"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Loader2, ArrowLeft } from "lucide-react";

interface CPVNode {
  cpv_code: string;
  title: string;
  children?: CPVNode[];
}

interface CPVBrowserProps {
  onSelect?: (code: string) => void;
}

export function CPVBrowser({ onSelect }: CPVBrowserProps) {
  const [divisions, setDivisions] = useState<CPVNode[]>([]);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<CPVNode[]>([]);
  const [selected, setSelected] = useState<CPVNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDivisions();
  }, []);

  async function loadDivisions() {
    try {
      setLoading(true);
      const res = await api.getCPVDivisions();
      setDivisions(res.divisions || []);
    } catch (err) {
      console.error("Failed to load CPV divisions:", err);
      setError("CPV хиерархијата не е достапна.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSelect(code: string) {
    try {
      setLoading(true);
      const res = await api.getCPVCode(code);
      const node: CPVNode = {
        cpv_code: res.cpv_code,
        title: res.title,
        children: res.children,
      };
      setSelected(node);
      if (onSelect) onSelect(code);
    } catch (err) {
      console.error("Failed to load CPV code:", err);
      setError("Не може да се вчита CPV записот.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSearch(q: string) {
    if (q.length < 2) {
      setResults([]);
      return;
    }
    try {
      setSearchLoading(true);
      const res = await api.searchCPVCodes(q, 20);
      // Map API response format (code, name) to CPVNode format (cpv_code, title)
      const mapped = (res.results || []).map(r => ({
        cpv_code: r.code,
        title: r.name_mk || r.name
      }));
      setResults(mapped);
    } catch (err) {
      console.error("Failed to search CPV:", err);
      setResults([]);
    } finally {
      setSearchLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>CPV Хиерархија</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Input
          placeholder="Пребарај CPV (минимум 2 букви)"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            void handleSearch(e.target.value);
          }}
        />
        {searchLoading && <p className="text-xs text-muted-foreground">Пребарување...</p>}
        {!searchLoading && results.length > 0 && (
          <div className="border rounded-md max-h-40 overflow-auto">
            {results.map((r) => (
              <button
                key={r.cpv_code}
                className="block w-full text-left px-3 py-2 hover:bg-accent text-sm"
                onClick={() => handleSelect(r.cpv_code)}
              >
                <span className="font-mono text-xs mr-2">{r.cpv_code}</span>
                {r.title}
              </button>
            ))}
          </div>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}
        {loading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}

        {!selected && !loading && (
          <div className="grid grid-cols-2 gap-2 text-sm">
            {divisions.map((d) => (
              <button
                key={d.cpv_code}
                className="border rounded-md px-2 py-2 hover:bg-accent text-left"
                onClick={() => handleSelect(d.cpv_code)}
              >
                <span className="font-mono text-xs mr-2">{d.cpv_code}</span>
                {d.title}
              </button>
            ))}
          </div>
        )}

        {selected && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold">{selected.title}</p>
                <p className="text-xs text-muted-foreground font-mono">{selected.cpv_code}</p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setSelected(null)}>
                <ArrowLeft className="h-4 w-4 mr-1" /> Назад
              </Button>
            </div>
            {selected.children && selected.children.length > 0 ? (
              <div className="grid grid-cols-1 gap-1 text-sm">
                {selected.children.map((child) => (
                  <button
                    key={child.cpv_code}
                    className="border rounded px-2 py-2 hover:bg-accent text-left"
                    onClick={() => handleSelect(child.cpv_code)}
                  >
                    <span className="font-mono text-xs mr-2">{child.cpv_code}</span>
                    {child.title}
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">Нема подкатегории.</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
