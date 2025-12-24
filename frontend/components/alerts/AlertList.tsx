'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { AlertCard } from './AlertCard';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent } from '@/components/ui/card';
import { Bell, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
interface Alert {
  id: string;
  name: string;
  alert_type: string;
  criteria: any;
  is_active: boolean;
  match_count?: number;
  created_at: string;
  updated_at?: string;
}

interface AlertListProps {
  onCreateClick?: () => void;
}

export function AlertList({ onCreateClick }: AlertListProps) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAlerts();
  }, []);

  const loadAlerts = async () => {
    try {
      setLoading(true);
      const data = await api.getAlerts();
      setAlerts(data.alerts || []);
    } catch (error: any) {
      console.error('Failed to load alerts:', error);
      toast.error('Грешка при вчитување на алертите');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (id: string, active: boolean) => {
    try {
      await api.updateAlert(id, { is_active: active });
      setAlerts((prev) =>
        prev.map((alert) =>
          alert.id === id ? { ...alert, is_active: active } : alert
        )
      );
      toast.success(active ? 'Алертот е активиран' : 'Алертот е паузиран');
    } catch (error: any) {
      console.error('Failed to toggle alert:', error);
      toast.error('Грешка при ажурирање на алертот');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Дали сте сигурни дека сакате да го избришете овој алерт?')) {
      return;
    }

    try {
      await api.deleteAlert(id);
      setAlerts((prev) => prev.filter((alert) => alert.id !== id));
      toast.success('Алертот е успешно избришан');
    } catch (error: any) {
      console.error('Failed to delete alert:', error);
      toast.error('Грешка при бришење на алертот');
    }
  };

  const handleEdit = (id: string) => {
    // Navigate to edit view (could be a modal or separate page)
    toast.info('Измена на алерти ќе биде достапна наскоро');
  };

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <Card key={i}>
            <CardContent className="p-6">
              <div className="space-y-3">
                <Skeleton className="h-6 w-1/3" />
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-8 w-full" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
          <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
            <Bell className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold mb-2">Немате алерти</h3>
          <p className="text-muted-foreground mb-4 max-w-md">
            Креирајте алерт за да добивате известувања за нови тендери кои се совпаѓаат со вашите критериуми.
          </p>
          <Button onClick={onCreateClick}>
            <Plus className="w-4 h-4 mr-2" />
            Креирај Алерт
          </Button>
        </CardContent>
      </Card>
    );
  }

  const activeAlerts = alerts.filter((a) => a.is_active);
  const inactiveAlerts = alerts.filter((a) => !a.is_active);

  return (
    <div className="space-y-6">
      {activeAlerts.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold mb-4">Активни Алерти ({activeAlerts.length})</h2>
          <div className="space-y-4">
            {activeAlerts.map((alert) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                onToggle={handleToggle}
                onEdit={handleEdit}
                onDelete={handleDelete}
              />
            ))}
          </div>
        </div>
      )}

      {inactiveAlerts.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold mb-4">Паузирани Алерти ({inactiveAlerts.length})</h2>
          <div className="space-y-4">
            {inactiveAlerts.map((alert) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                onToggle={handleToggle}
                onEdit={handleEdit}
                onDelete={handleDelete}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
