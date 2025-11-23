import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Политика за приватност",
  description: "Политика за приватност на Nabavkidata.com - како ги чуваме и користиме вашите податоци.",
};

export default function PrivacyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
