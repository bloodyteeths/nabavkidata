import { Metadata } from "next";
import DashboardLayout from "@/components/layout/DashboardLayout";

export const metadata: Metadata = {
  title: "Добавувачи",
  description: "Преглед на добавувачи и нивна историја на учество во тендери.",
};

export default function SuppliersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
