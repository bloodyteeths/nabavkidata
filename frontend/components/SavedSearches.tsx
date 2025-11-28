"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Bookmark, Play, Trash2, Loader2 } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { api } from "@/lib/api";
import { toast } from "sonner";

interface SavedSearch {
  id: string;
  name: string;
  filters: {
    search?: string;
    category?: string;
    status?: string;
    cpvCode?: string;
    minBudget?: number;
    maxBudget?: number;
    entity?: string;
    dateFrom?: string;
    dateTo?: string;
  };
  created_at: string;
}

interface SavedSearchesProps {
  currentFilters: any;
  onLoadSearch: (filters: any) => void;
}

export function SavedSearches({ currentFilters, onLoadSearch }: SavedSearchesProps) {
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [newSearchName, setNewSearchName] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadSearches();
  }, []);

  const loadSearches = async () => {
    try {
      setLoading(true);
      const result = await api.getSavedSearches();
      setSearches(result.items || []);
    } catch (error) {
      console.error("Failed to load saved searches:", error);
      // Fallback to localStorage if API fails
      const saved = localStorage.getItem("nabavki_saved_searches");
      if (saved) {
        setSearches(JSON.parse(saved));
      }
    } finally {
      setLoading(false);
    }
  };

  const saveSearch = async () => {
    if (!newSearchName.trim()) return;

    try {
      setSaving(true);
      const result = await api.createSavedSearch({
        name: newSearchName,
        filters: currentFilters
      });
      setSearches(prev => [...prev, result]);
      setNewSearchName("");
      setIsDialogOpen(false);
      toast.success("Пребарувањето е зачувано");
    } catch (error: any) {
      console.error("Failed to save search:", error);
      toast.error(error.message || "Не успеавме да зачуваме пребарување");
    } finally {
      setSaving(false);
    }
  };

  const deleteSearch = async (id: string) => {
    try {
      await api.deleteSavedSearch(id);
      setSearches(prev => prev.filter(s => s.id !== id));
      toast.success("Пребарувањето е избришано");
    } catch (error) {
      console.error("Failed to delete saved search:", error);
      toast.error("Бришењето не успеа");
    }
  };

  const runSearch = (search: SavedSearch) => {
    onLoadSearch(search.filters);
  };

  const hasActiveFilters = Object.values(currentFilters).some(v => v && v !== "");

  // Helper to format filter labels in Macedonian
  const formatFilterLabel = (key: string): string => {
    const labels: Record<string, string> = {
      search: "Пребарување",
      category: "Категорија",
      status: "Статус",
      cpvCode: "CPV код",
      minBudget: "Мин. буџет",
      maxBudget: "Макс. буџет",
      entity: "Наручилац",
      dateFrom: "Од датум",
      dateTo: "До датум",
    };
    return labels[key] || key;
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">Зачувани пребарувања</CardTitle>
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm" variant="outline" disabled={!hasActiveFilters}>
                <Bookmark className="h-4 w-4 mr-1" />
                Зачувај
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Зачувај пребарување</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <Input
                  placeholder="Име на пребарувањето..."
                  value={newSearchName}
                  onChange={(e) => setNewSearchName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") saveSearch();
                  }}
                />
                <div className="text-sm text-muted-foreground">
                  Активни филтри:
                  <div className="flex flex-wrap gap-1 mt-2">
                    {Object.entries(currentFilters).map(([key, value]) =>
                      value ? (
                        <Badge key={key} variant="secondary">
                          {formatFilterLabel(key)}: {String(value)}
                        </Badge>
                      ) : null
                    )}
                  </div>
                </div>
                <Button onClick={saveSearch} className="w-full" disabled={!newSearchName.trim() || saving}>
                  {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Зачувај
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Се вчитуваат...
          </div>
        ) : searches.length === 0 ? (
          <p className="text-sm text-muted-foreground">Нема зачувани пребарувања</p>
        ) : (
          <div className="space-y-2">
            {searches.map(search => (
              <div key={search.id} className="flex items-center justify-between p-2 rounded border">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{search.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(search.created_at, { year: "numeric", month: "2-digit", day: "2-digit" })}
                  </p>
                </div>
                <div className="flex gap-1">
                  <Button size="icon" variant="ghost" onClick={() => runSearch(search)} title="Изврши">
                    <Play className="h-4 w-4" />
                  </Button>
                  <Button size="icon" variant="ghost" onClick={() => deleteSearch(search.id)} title="Избриши">
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
