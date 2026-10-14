import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Услови за користење",
  description: "Услови за користење на nabavkidata.com и услугата за подготовка на тендерски понуди (Фактурино ДООЕЛ).",
};

export default function TermsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
