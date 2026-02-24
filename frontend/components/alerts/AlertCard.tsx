'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Edit, Pause, Trash2, Play } from 'lucide-react';
import { useState } from 'react';

interface AlertCardProps {
  alert: {
    id: string;
    name: string;
    alert_type: string;
    criteria: any;
    is_active: boolean;
    match_count?: number;
    created_at: string;
  };
  onToggle: (id: string, active: boolean) => void;
  onEdit?: (id: string) => void;
  onDelete: (id: string) => void;
}

export function AlertCard({ alert, onToggle, onEdit, onDelete }: AlertCardProps) {
  const [isActive, setIsActive] = useState(alert.is_active);

  const handleToggle = async (checked: boolean) => {
    setIsActive(checked);
    await onToggle(alert.id, checked);
  };

  const getAlertTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      keyword: 'Клучен збор',
      cpv_code: 'CPV Код',
      entity: 'Институција',
      competitor: 'Конкурент',
      budget_range: 'Буџет опсег',
    };
    return labels[type] || type;
  };

  const getCriteriaSummary = () => {
    const parts: string[] = [];
    const MAX_ITEMS = 5;

    if (alert.criteria.keywords?.length > 0) {
      const kw = alert.criteria.keywords;
      const shown = kw.slice(0, MAX_ITEMS).join(', ');
      const extra = kw.length > MAX_ITEMS ? ` +${kw.length - MAX_ITEMS} повеќе` : '';
      parts.push(`Клучни зборови: ${shown}${extra}`);
    }
    if (alert.criteria.cpv_codes?.length > 0) {
      const codes = alert.criteria.cpv_codes;
      const shown = codes.slice(0, 3).join(', ');
      const extra = codes.length > 3 ? ` +${codes.length - 3}` : '';
      parts.push(`CPV: ${shown}${extra}`);
    }
    if (alert.criteria.entities?.length > 0) {
      const ent = alert.criteria.entities;
      const shown = ent.slice(0, 2).join(', ');
      const extra = ent.length > 2 ? ` +${ent.length - 2}` : '';
      parts.push(`Институции: ${shown}${extra}`);
    }
    if (alert.criteria.competitors?.length > 0) {
      const comp = alert.criteria.competitors;
      const shown = comp.slice(0, 2).join(', ');
      const extra = comp.length > 2 ? ` +${comp.length - 2}` : '';
      parts.push(`Конкуренти: ${shown}${extra}`);
    }
    if (alert.criteria.min_budget || alert.criteria.max_budget) {
      const min = alert.criteria.min_budget ? `${alert.criteria.min_budget.toLocaleString()} МКД` : '∞';
      const max = alert.criteria.max_budget ? `${alert.criteria.max_budget.toLocaleString()} МКД` : '∞';
      parts.push(`Буџет: ${min} - ${max}`);
    }

    return parts.join(' • ');
  };

  return (
    <Card className={`${!isActive ? 'opacity-60' : ''} transition-opacity`}>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <CardTitle className="text-lg">{alert.name}</CardTitle>
              <Badge variant="secondary">{getAlertTypeLabel(alert.alert_type)}</Badge>
              {alert.match_count !== undefined && alert.match_count > 0 && (
                <Badge variant="default" className="bg-green-500">
                  {alert.match_count} нови
                </Badge>
              )}
            </div>
            <CardDescription className="text-sm line-clamp-2">
              {getCriteriaSummary()}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2 ml-4">
            <Switch checked={isActive} onCheckedChange={handleToggle} />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between gap-2">
          <div className="text-xs text-muted-foreground">
            Креирано: {alert.created_at ? new Date(alert.created_at).toLocaleDateString('mk-MK') : '-'}
          </div>
          <div className="flex items-center gap-2">
            {onEdit && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onEdit(alert.id)}
              >
                <Edit className="w-4 h-4 mr-1" />
                Измени
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleToggle(!isActive)}
            >
              {isActive ? (
                <>
                  <Pause className="w-4 h-4 mr-1" />
                  Пауза
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-1" />
                  Активирај
                </>
              )}
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => onDelete(alert.id)}
            >
              <Trash2 className="w-4 h-4 mr-1" />
              Избриши
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
