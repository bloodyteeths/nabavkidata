import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Услови за користење",
  description: "Услови за користење на Nabavkidata.com платформата за јавни набавки.",
};

export default function TermsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
