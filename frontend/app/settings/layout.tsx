import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Поставки",
  description: "Управувајте со вашите преференци, претплата и профил на Nabavkidata.com.",
};

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
