import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Наплата",
  description: "Управувајте со вашата претплата, историја на наплата и користење на услугата.",
};

export default function BillingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
