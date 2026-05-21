'use client';

import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AlertList } from '@/components/alerts/AlertList';
import { AlertCreator } from '@/components/alerts/AlertCreator';
import { AlertMatches } from '@/components/alerts/AlertMatches';
import { Bell, Plus, Inbox } from 'lucide-react';
import { PageContainer } from '@/components/ui/page-container';
import { PageHeader } from '@/components/ui/page-header';
import { Suspense } from 'react';

function AlertsContent() {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get('tab') || 'alerts';
  const [activeTab, setActiveTab] = useState(initialTab);

  return (
    <PageContainer>
      <PageHeader
        icon={Bell}
        title="Паметни Алерти"
        description="Никогаш не пропуштајте релевантен тендер"
      />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3 lg:w-auto">
          <TabsTrigger value="alerts" className="flex items-center gap-2">
            <Bell className="w-4 h-4" />
            <span className="hidden sm:inline">Мои Алерти</span>
            <span className="sm:hidden">Алерти</span>
          </TabsTrigger>
          <TabsTrigger value="matches" className="flex items-center gap-2">
            <Inbox className="w-4 h-4" />
            <span className="hidden sm:inline">Совпаѓања</span>
            <span className="sm:hidden">Inbox</span>
          </TabsTrigger>
          <TabsTrigger value="create" className="flex items-center gap-2">
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">Креирај Алерт</span>
            <span className="sm:hidden">Нов</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="alerts" className="mt-6">
          <AlertList onCreateClick={() => setActiveTab('create')} />
        </TabsContent>
        <TabsContent value="matches" className="mt-6">
          <AlertMatches />
        </TabsContent>
        <TabsContent value="create" className="mt-6">
          <AlertCreator onCreated={() => setActiveTab('alerts')} />
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}

export default function AlertsPage() {
  return (
    <Suspense fallback={<PageContainer><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mt-20" /></PageContainer>}>
      <AlertsContent />
    </Suspense>
  );
}
