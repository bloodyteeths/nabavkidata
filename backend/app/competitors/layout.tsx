import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Следење на Конкуренти",
  description: "Анализа на активности и успеси на вашите конкуренти во јавните набавки.",
};

import DashboardLayout from "@/components/layout/DashboardLayout";

export default function CompetitorsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
