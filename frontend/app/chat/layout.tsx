import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Прашања за тендери",
  description: "Основни одговори за тендерите од нашата база. Понудите ги подготвува нашиот тим.",
};

import DashboardLayout from "@/components/layout/DashboardLayout";

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
