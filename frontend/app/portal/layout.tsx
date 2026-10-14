import type { Metadata } from 'next';
import DashboardLayout from '@/components/layout/DashboardLayout';
import PortalGate from '@/components/bid-service/PortalGate';

export const metadata: Metadata = {
  title: 'Портал',
  description: 'Вашите понуди, документи и рокови.',
};

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <DashboardLayout>
      <PortalGate>{children}</PortalGate>
    </DashboardLayout>
  );
}
