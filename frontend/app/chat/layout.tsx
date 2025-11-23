import { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Асистент",
  description: "Поставете прашања за тендерите и добијте AI-базирани одговори и анализа.",
};

import DashboardLayout from "@/components/layout/DashboardLayout";

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
