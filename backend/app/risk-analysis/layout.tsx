import { Metadata } from "next";
import DashboardLayout from "@/components/layout/DashboardLayout";

export const metadata: Metadata = {
  title: "Анализа на ризик",
  description: "AI агенти за детекција на корупциски ризици во тендери, компании и институции.",
};

export default function RiskAnalysisLayout({ children }: { children: React.ReactNode }) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
