import { Metadata } from "next";
import DashboardLayout from "@/components/layout/DashboardLayout";

export const metadata: Metadata = {
  title: "Истражувач на Тендери",
  description: "Пребарувајте и филтрирајте тендери од целата база на јавни набавки во Македонија.",
};

export default function TendersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
