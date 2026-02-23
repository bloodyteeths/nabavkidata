import { Metadata } from "next";
import DashboardLayout from "@/components/layout/DashboardLayout";

export const metadata: Metadata = {
  title: "Каталог на Производи | NabavkiData",
  description: "Пребарувајте и споредувајте производи, опрема и услуги низ сите јавни набавки во Македонија.",
};

export default function ProductsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
