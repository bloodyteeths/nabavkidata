'use client';

import { useState } from 'react';
import { Bell, BellRing, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';

interface AlertBellButtonProps {
  tenderId: string;
  cpvCode?: string;
  procuringEntity?: string;
  title?: string;
  size?: 'sm' | 'default';
}

export function AlertBellButton({
  tenderId,
  cpvCode,
  procuringEntity,
  title,
  size = 'sm',
}: AlertBellButtonProps) {
  const { isAuthenticated } = useAuth();
  const [isWatching, setIsWatching] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleClick = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!isAuthenticated) {
      toast.error('Најавете се за да креирате алерт');
      return;
    }

    if (isWatching) {
      toast.info('Веќе следите слични тендери');
      return;
    }

    if (!cpvCode && !procuringEntity) {
      toast.error('Нема доволно податоци за креирање алерт');
      return;
    }

    try {
      setLoading(true);
      await api.quickSubscribeFromTender({
        tender_id: tenderId,
        cpv_code: cpvCode,
        procuring_entity: procuringEntity,
        title,
      });
      setIsWatching(true);
      toast.success('Алерт креиран! Ќе добиете известување за слични тендери.');
    } catch (err: any) {
      toast.error(err.message || 'Грешка при креирање на алерт');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button
      size={size}
      variant={isWatching ? 'default' : 'outline'}
      onClick={handleClick}
      disabled={loading}
      title={isWatching ? 'Следите слични тендери' : 'Следи слични тендери'}
      className="flex-shrink-0"
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : isWatching ? (
        <BellRing className="h-4 w-4" />
      ) : (
        <Bell className="h-4 w-4" />
      )}
    </Button>
  );
}
