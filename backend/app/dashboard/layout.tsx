import { Metadata } from "next";
import DashboardLayout from "@/components/layout/DashboardLayout";

export const metadata: Metadata = {
  title: "Табла",
  description: "Персонализирана табла со препорачани тендери, инсајти и анализа на конкуренцијата.",
};

export default function DashboardPageLayout({ children }: { children: React.ReactNode }) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
