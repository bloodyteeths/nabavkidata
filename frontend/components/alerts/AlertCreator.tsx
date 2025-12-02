'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { X, Plus } from 'lucide-react';

interface AlertCreatorProps {
  onCreated: () => void;
}

export function AlertCreator({ onCreated }: AlertCreatorProps) {
  const [name, setName] = useState('');
  const [alertType, setAlertType] = useState<string>('keyword');
  const [keywords, setKeywords] = useState<string[]>([]);
  const [keywordInput, setKeywordInput] = useState('');
  const [cpvCodes, setCpvCodes] = useState<string[]>([]);
  const [cpvInput, setCpvInput] = useState('');
  const [entities, setEntities] = useState<string[]>([]);
  const [entityInput, setEntityInput] = useState('');
  const [competitors, setCompetitors] = useState<string[]>([]);
  const [competitorInput, setCompetitorInput] = useState('');
  const [minBudget, setMinBudget] = useState('');
  const [maxBudget, setMaxBudget] = useState('');
  const [emailEnabled, setEmailEnabled] = useState(true);
  const [inAppEnabled, setInAppEnabled] = useState(true);
  const [loading, setLoading] = useState(false);
  const [cpvSuggestions, setCpvSuggestions] = useState<any[]>([]);
  const [entitySuggestions, setEntitySuggestions] = useState<any[]>([]);

  // Fetch CPV code suggestions
  useEffect(() => {
    if (cpvInput.length >= 2) {
      const fetchCpvSuggestions = async () => {
        try {
          const data = await api.searchCPVCodes(cpvInput, 10);
          setCpvSuggestions(data.results || []);
        } catch (error) {
          console.error('Failed to fetch CPV suggestions:', error);
        }
      };
      const timer = setTimeout(fetchCpvSuggestions, 300);
      return () => clearTimeout(timer);
    } else {
      setCpvSuggestions([]);
    }
  }, [cpvInput]);

  // Fetch entity suggestions
  useEffect(() => {
    if (entityInput.length >= 2) {
      const fetchEntitySuggestions = async () => {
        try {
          const data = await api.searchEntities(entityInput, 10);
          setEntitySuggestions(data.items || []);
        } catch (error) {
          console.error('Failed to fetch entity suggestions:', error);
        }
      };
      const timer = setTimeout(fetchEntitySuggestions, 300);
      return () => clearTimeout(timer);
    } else {
      setEntitySuggestions([]);
    }
  }, [entityInput]);

  const addKeyword = () => {
    if (keywordInput.trim() && !keywords.includes(keywordInput.trim())) {
      setKeywords([...keywords, keywordInput.trim()]);
      setKeywordInput('');
    }
  };

  const removeKeyword = (keyword: string) => {
    setKeywords(keywords.filter((k) => k !== keyword));
  };

  const addCpvCode = (code: string) => {
    if (!cpvCodes.includes(code)) {
      setCpvCodes([...cpvCodes, code]);
      setCpvInput('');
      setCpvSuggestions([]);
    }
  };

  const removeCpvCode = (code: string) => {
    setCpvCodes(cpvCodes.filter((c) => c !== code));
  };

  const addEntity = (entityName: string) => {
    if (!entities.includes(entityName)) {
      setEntities([...entities, entityName]);
      setEntityInput('');
      setEntitySuggestions([]);
    }
  };

  const removeEntity = (entityName: string) => {
    setEntities(entities.filter((e) => e !== entityName));
  };

  const addCompetitor = () => {
    if (competitorInput.trim() && !competitors.includes(competitorInput.trim())) {
      setCompetitors([...competitors, competitorInput.trim()]);
      setCompetitorInput('');
    }
  };

  const removeCompetitor = (competitor: string) => {
    setCompetitors(competitors.filter((c) => c !== competitor));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      toast.error('Внесете име на алертот');
      return;
    }

    const criteria: any = {};

    if (keywords.length > 0) criteria.keywords = keywords;
    if (cpvCodes.length > 0) criteria.cpv_codes = cpvCodes;
    if (entities.length > 0) criteria.entities = entities;
    if (competitors.length > 0) criteria.competitors = competitors;
    if (minBudget) criteria.min_budget = parseFloat(minBudget);
    if (maxBudget) criteria.max_budget = parseFloat(maxBudget);

    if (Object.keys(criteria).length === 0) {
      toast.error('Додадете најмалку еден критериум');
      return;
    }

    const channels: string[] = [];
    if (emailEnabled) channels.push('email');
    if (inAppEnabled) channels.push('in_app');

    try {
      setLoading(true);
      await api.createAlert({
        name: name.trim(),
        alert_type: alertType,
        criteria,
        channels,
      });
      toast.success('Алертот е успешно креиран');
      onCreated();
      // Reset form
      setName('');
      setKeywords([]);
      setCpvCodes([]);
      setEntities([]);
      setCompetitors([]);
      setMinBudget('');
      setMaxBudget('');
    } catch (error: any) {
      console.error('Failed to create alert:', error);
      toast.error(error.message || 'Грешка при креирање на алертот');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Креирај Нов Алерт</CardTitle>
        <CardDescription>
          Дефинирајте критериуми за да добивате известувања за релевантни тендери
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Alert Name */}
          <div className="space-y-2">
            <Label htmlFor="name">Име на Алерт *</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="нпр. IT Опрема за Скопје"
              required
            />
          </div>

          {/* Alert Type */}
          <div className="space-y-2">
            <Label htmlFor="type">Тип на Алерт</Label>
            <select
              id="type"
              value={alertType}
              onChange={(e) => setAlertType(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="keyword">Клучен збор</option>
              <option value="cpv_code">CPV Код</option>
              <option value="entity">Институција</option>
              <option value="competitor">Конкурент</option>
              <option value="budget_range">Буџет опсег</option>
            </select>
          </div>

          {/* Keywords */}
          <div className="space-y-2">
            <Label>Клучни Зборови</Label>
            <div className="flex gap-2">
              <Input
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addKeyword())}
                placeholder="Додај клучен збор..."
              />
              <Button type="button" onClick={addKeyword} variant="outline">
                <Plus className="w-4 h-4" />
              </Button>
            </div>
            {keywords.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {keywords.map((keyword) => (
                  <Badge key={keyword} variant="secondary" className="gap-1">
                    {keyword}
                    <X
                      className="w-3 h-3 cursor-pointer"
                      onClick={() => removeKeyword(keyword)}
                    />
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* CPV Codes */}
          <div className="space-y-2">
            <Label>CPV Кодови</Label>
            <div className="relative">
              <Input
                value={cpvInput}
                onChange={(e) => setCpvInput(e.target.value)}
                placeholder="Барај CPV код..."
              />
              {cpvSuggestions.length > 0 && (
                <div className="absolute z-10 w-full mt-1 bg-background border rounded-md shadow-lg max-h-60 overflow-auto">
                  {cpvSuggestions.map((cpv) => (
                    <div
                      key={cpv.code}
                      className="px-3 py-2 hover:bg-muted cursor-pointer"
                      onClick={() => addCpvCode(cpv.code)}
                    >
                      <div className="font-medium">{cpv.code}</div>
                      <div className="text-sm text-muted-foreground">{cpv.name_mk || cpv.name}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {cpvCodes.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {cpvCodes.map((code) => (
                  <Badge key={code} variant="secondary" className="gap-1">
                    {code}
                    <X
                      className="w-3 h-3 cursor-pointer"
                      onClick={() => removeCpvCode(code)}
                    />
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Entities */}
          <div className="space-y-2">
            <Label>Институции</Label>
            <div className="relative">
              <Input
                value={entityInput}
                onChange={(e) => setEntityInput(e.target.value)}
                placeholder="Барај институција..."
              />
              {entitySuggestions.length > 0 && (
                <div className="absolute z-10 w-full mt-1 bg-background border rounded-md shadow-lg max-h-60 overflow-auto">
                  {entitySuggestions.map((entity) => (
                    <div
                      key={entity.entity_id}
                      className="px-3 py-2 hover:bg-muted cursor-pointer"
                      onClick={() => addEntity(entity.entity_name)}
                    >
                      <div className="font-medium">{entity.entity_name}</div>
                      <div className="text-sm text-muted-foreground">
                        {entity.total_tenders} тендери
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {entities.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {entities.map((entity) => (
                  <Badge key={entity} variant="secondary" className="gap-1">
                    {entity}
                    <X
                      className="w-3 h-3 cursor-pointer"
                      onClick={() => removeEntity(entity)}
                    />
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Competitors */}
          <div className="space-y-2">
            <Label>Конкуренти за следење</Label>
            <div className="flex gap-2">
              <Input
                value={competitorInput}
                onChange={(e) => setCompetitorInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addCompetitor())}
                placeholder="Додај конкурент..."
              />
              <Button type="button" onClick={addCompetitor} variant="outline">
                <Plus className="w-4 h-4" />
              </Button>
            </div>
            {competitors.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {competitors.map((competitor) => (
                  <Badge key={competitor} variant="secondary" className="gap-1">
                    {competitor}
                    <X
                      className="w-3 h-3 cursor-pointer"
                      onClick={() => removeCompetitor(competitor)}
                    />
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Budget Range */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="minBudget">Мин. Буџет (МКД)</Label>
              <Input
                id="minBudget"
                type="number"
                value={minBudget}
                onChange={(e) => setMinBudget(e.target.value)}
                placeholder="0"
                min="0"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="maxBudget">Макс. Буџет (МКД)</Label>
              <Input
                id="maxBudget"
                type="number"
                value={maxBudget}
                onChange={(e) => setMaxBudget(e.target.value)}
                placeholder="∞"
                min="0"
              />
            </div>
          </div>

          {/* Notification Channels */}
          <div className="space-y-3">
            <Label>Канали за известување</Label>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="email"
                checked={emailEnabled}
                onCheckedChange={(checked) => setEmailEnabled(checked as boolean)}
              />
              <label
                htmlFor="email"
                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >
                Email известувања
              </label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="inApp"
                checked={inAppEnabled}
                onCheckedChange={(checked) => setInAppEnabled(checked as boolean)}
              />
              <label
                htmlFor="inApp"
                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >
                Известувања во апликација
              </label>
            </div>
          </div>

          <div className="flex gap-2">
            <Button type="submit" disabled={loading}>
              {loading ? 'Креирање...' : 'Креирај Алерт'}
            </Button>
            <Button type="button" variant="outline" onClick={() => onCreated()}>
              Откажи
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
