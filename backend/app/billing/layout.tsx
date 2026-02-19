import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Наплата",
  description: "Управувајте со вашата претплата, историја на наплата и користење на услугата.",
};

import DashboardLayout from "@/components/layout/DashboardLayout";

export default function BillingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
