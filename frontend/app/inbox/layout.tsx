import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Приемно сандаче",
  description: "Преглед на е-мејл дигести и системски известувања за тендери.",
};

export default function InboxLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
