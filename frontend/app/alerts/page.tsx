'use client';

import { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AlertList } from '@/components/alerts/AlertList';
import { AlertCreator } from '@/components/alerts/AlertCreator';
import { AlertMatches } from '@/components/alerts/AlertMatches';
import { Bell, Plus, Inbox } from 'lucide-react';

export default function AlertsPage() {
  const [activeTab, setActiveTab] = useState('alerts');

  return (
    <div className="container mx-auto py-6 px-4">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold">Паметни Алерти</h1>
          <p className="text-muted-foreground">Никогаш не пропуштајте релевантен тендер</p>
        </div>
      </div>

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
          <AlertList />
        </TabsContent>
        <TabsContent value="matches" className="mt-6">
          <AlertMatches />
        </TabsContent>
        <TabsContent value="create" className="mt-6">
          <AlertCreator onCreated={() => setActiveTab('alerts')} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
