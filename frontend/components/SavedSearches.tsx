"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Bookmark, Play, Trash2, Bell, BellOff } from "lucide-react";

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
  alertEnabled: boolean;
  createdAt: string;
  lastRun?: string;
}

interface SavedSearchesProps {
  currentFilters: any;
  onLoadSearch: (filters: any) => void;
}

export function SavedSearches({ currentFilters, onLoadSearch }: SavedSearchesProps) {
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [newSearchName, setNewSearchName] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  useEffect(() => {
    // Load saved searches from localStorage
    const saved = localStorage.getItem("nabavki_saved_searches");
    if (saved) {
      setSearches(JSON.parse(saved));
    }
  }, []);

  const saveSearch = () => {
    if (!newSearchName.trim()) return;

    const newSearch: SavedSearch = {
      id: Date.now().toString(),
      name: newSearchName,
      filters: currentFilters,
      alertEnabled: false,
      createdAt: new Date().toISOString(),
    };

    const updated = [...searches, newSearch];
    setSearches(updated);
    localStorage.setItem("nabavki_saved_searches", JSON.stringify(updated));
    setNewSearchName("");
    setIsDialogOpen(false);
  };

  const deleteSearch = (id: string) => {
    const updated = searches.filter(s => s.id !== id);
    setSearches(updated);
    localStorage.setItem("nabavki_saved_searches", JSON.stringify(updated));
  };

  const toggleAlert = (id: string) => {
    const updated = searches.map(s =>
      s.id === id ? { ...s, alertEnabled: !s.alertEnabled } : s
    );
    setSearches(updated);
    localStorage.setItem("nabavki_saved_searches", JSON.stringify(updated));
  };

  const runSearch = (search: SavedSearch) => {
    onLoadSearch(search.filters);
    // Update lastRun
    const updated = searches.map(s =>
      s.id === search.id ? { ...s, lastRun: new Date().toISOString() } : s
    );
    setSearches(updated);
    localStorage.setItem("nabavki_saved_searches", JSON.stringify(updated));
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
                <Button onClick={saveSearch} className="w-full" disabled={!newSearchName.trim()}>
                  Зачувај
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent>
        {searches.length === 0 ? (
          <p className="text-sm text-muted-foreground">Нема зачувани пребарувања</p>
        ) : (
          <div className="space-y-2">
            {searches.map(search => (
              <div key={search.id} className="flex items-center justify-between p-2 rounded border">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{search.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(search.createdAt).toLocaleDateString("mk-MK")}
                  </p>
                </div>
                <div className="flex gap-1">
                  <Button size="icon" variant="ghost" onClick={() => runSearch(search)} title="Изврши">
                    <Play className="h-4 w-4" />
                  </Button>
                  <Button size="icon" variant="ghost" onClick={() => toggleAlert(search.id)} title="Известувања">
                    {search.alertEnabled ? <Bell className="h-4 w-4 text-primary" /> : <BellOff className="h-4 w-4" />}
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
