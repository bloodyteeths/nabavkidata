import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Наплата",
  description: "Услугата за подготовка на тендерски понуди: плаќање со фактура од Фактурино ДООЕЛ.",
};

import DashboardLayout from "@/components/layout/DashboardLayout";

export default function BillingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
