import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Регистрација",
  robots: { index: false, follow: true },
};

export default function RegisterLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
