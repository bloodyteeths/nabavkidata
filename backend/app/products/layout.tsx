import { Metadata } from "next";
import DashboardLayout from "@/components/layout/DashboardLayout";

export const metadata: Metadata = {
  title: "Пребарување на Производи | NabavkiData",
  description: "Пребарувајте и анализирајте производи, медикаменти, опрема и услуги кои се јавувачи во јавни набавки.",
};

export default function ProductsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
