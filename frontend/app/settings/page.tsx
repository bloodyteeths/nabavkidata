"use client";

import { useState, useEffect } from "react";
import { api, UserPreferences } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { X } from "lucide-react";

const AVAILABLE_SECTORS = ["ИТ", "Градежништво", "Консултинг", "Опрема"];

const DEFAULT_PREFERENCES: UserPreferences = {
  sectors: [],
  cpv_codes: [],
  entities: [],
  min_budget: undefined,
  max_budget: undefined,
  exclude_keywords: [],
  competitor_companies: [],
  notification_frequency: "daily",
  email_enabled: true,
};

export default function SettingsPage() {
  const [preferences, setPreferences] = useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [cpvInput, setCpvInput] = useState("");
  const [entityInput, setEntityInput] = useState("");
  const [keywordInput, setKeywordInput] = useState("");
  const [competitorInput, setCompetitorInput] = useState("");
  const userId = "demo-user";

  useEffect(() => {
    loadPreferences();
  }, []);

  const loadPreferences = async () => {
    try {
      setLoading(true);
      const prefs = await api.getPreferences(userId);
      setPreferences(prefs);
    } catch (error) {
      console.error("Грешка при вчитување на преференци:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      await api.updatePreferences(userId, preferences);
      console.log("Преференциите се успешно зачувани");
    } catch (error) {
      console.error("Грешка при зачувување:", error);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setPreferences(DEFAULT_PREFERENCES);
    console.log("Преференциите се ресетирани на стандардни");
  };

  const toggleSector = (sector: string) => {
    setPreferences((prev) => ({ ...prev, sectors: prev.sectors.includes(sector) ? prev.sectors.filter((s) => s !== sector) : [...prev.sectors, sector] }));
  };

  const addItem = (field: keyof UserPreferences, value: string, setter: (v: string) => void) => {
    if (value.trim() && !(preferences[field] as string[]).includes(value.trim())) {
      setPreferences((prev) => ({ ...prev, [field]: [...(prev[field] as string[]), value.trim()] }));
      setter("");
    }
  };

  const removeItem = (field: keyof UserPreferences, value: string) => {
    setPreferences((prev) => ({ ...prev, [field]: (prev[field] as string[]).filter((i) => i !== value) }));
  };

  if (loading) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-center">Се вчитува...</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 max-w-4xl">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Поставки</h1>
        <p className="text-muted-foreground mt-2">Управувајте со вашите преференци за нотификации</p>
      </div>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Сектори</CardTitle>
            <CardDescription>Изберете ги секторите што ве интересираат</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {AVAILABLE_SECTORS.map((sector) => (
                <Badge key={sector} variant={preferences.sectors.includes(sector) ? "default" : "outline"} className="cursor-pointer" onClick={() => toggleSector(sector)}>{sector}</Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>CPV Кодови</CardTitle>
            <CardDescription>Додадете CPV кодови за специфични категории</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-3">
              <Input placeholder="Внесете CPV код" value={cpvInput} onChange={(e) => setCpvInput(e.target.value)} onKeyPress={(e) => e.key === "Enter" && addItem("cpv_codes", cpvInput, setCpvInput)} />
              <Button onClick={() => addItem("cpv_codes", cpvInput, setCpvInput)}>Додади</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {preferences.cpv_codes.map((code) => (
                <Badge key={code} variant="secondary" className="gap-1">{code}<X className="h-3 w-3 cursor-pointer" onClick={() => removeItem("cpv_codes", code)} /></Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Ентитети</CardTitle>
            <CardDescription>Додадете набавувачки организации што ве интересираат</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-3">
              <Input placeholder="Внесете име на ентитет" value={entityInput} onChange={(e) => setEntityInput(e.target.value)} onKeyPress={(e) => e.key === "Enter" && addItem("entities", entityInput, setEntityInput)} />
              <Button onClick={() => addItem("entities", entityInput, setEntityInput)}>Додади</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {preferences.entities.map((entity) => (
                <Badge key={entity} variant="secondary" className="gap-1">{entity}<X className="h-3 w-3 cursor-pointer" onClick={() => removeItem("entities", entity)} /></Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Буџет</CardTitle>
            <CardDescription>Дефинирајте минимален и максимален буџет (МКД)</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Минимален буџет</label>
                <Input type="number" placeholder="0" value={preferences.min_budget || ""} onChange={(e) => setPreferences((prev) => ({ ...prev, min_budget: e.target.value ? Number(e.target.value) : undefined }))} />
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">Максимален буџет</label>
                <Input type="number" placeholder="∞" value={preferences.max_budget || ""} onChange={(e) => setPreferences((prev) => ({ ...prev, max_budget: e.target.value ? Number(e.target.value) : undefined }))} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Исклучени клучни зборови</CardTitle>
            <CardDescription>Тендери што содржат овие зборови нема да се прикажуваат</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-3">
              <Input placeholder="Внесете клучен збор" value={keywordInput} onChange={(e) => setKeywordInput(e.target.value)} onKeyPress={(e) => e.key === "Enter" && addItem("exclude_keywords", keywordInput, setKeywordInput)} />
              <Button onClick={() => addItem("exclude_keywords", keywordInput, setKeywordInput)}>Додади</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {preferences.exclude_keywords.map((keyword) => (
                <Badge key={keyword} variant="destructive" className="gap-1">{keyword}<X className="h-3 w-3 cursor-pointer" onClick={() => removeItem("exclude_keywords", keyword)} /></Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Конкурентски компании</CardTitle>
            <CardDescription>Следете ги активностите на конкурентските компании</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-3">
              <Input placeholder="Внесете име на компанија" value={competitorInput} onChange={(e) => setCompetitorInput(e.target.value)} onKeyPress={(e) => e.key === "Enter" && addItem("competitor_companies", competitorInput, setCompetitorInput)} />
              <Button onClick={() => addItem("competitor_companies", competitorInput, setCompetitorInput)}>Додади</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {preferences.competitor_companies.map((competitor) => (
                <Badge key={competitor} variant="warning" className="gap-1">{competitor}<X className="h-3 w-3 cursor-pointer" onClick={() => removeItem("competitor_companies", competitor)} /></Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Нотификации</CardTitle>
            <CardDescription>Конфигурирајте како сакате да примате нотификации</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Фреквенција на нотификации</label>
                <Select value={preferences.notification_frequency} onValueChange={(value) => setPreferences((prev) => ({ ...prev, notification_frequency: value }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="instant">Моментално</SelectItem>
                    <SelectItem value="daily">Дневно</SelectItem>
                    <SelectItem value="weekly">Неделно</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" id="email-enabled" checked={preferences.email_enabled} onChange={(e) => setPreferences((prev) => ({ ...prev, email_enabled: e.target.checked }))} className="w-4 h-4 cursor-pointer" />
                <label htmlFor="email-enabled" className="text-sm font-medium cursor-pointer">Овозможи email нотификации</label>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="flex gap-3 justify-end">
          <Button variant="outline" onClick={handleReset}>Ресетирај</Button>
          <Button onClick={handleSave} disabled={saving}>{saving ? "Се зачувува..." : "Зачувај"}</Button>
        </div>
      </div>
    </div>
  );
}
