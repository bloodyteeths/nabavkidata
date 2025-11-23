import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Регистрација",
  description: "Создадете нов профил на Nabavkidata.com и започнете да ги следите јавните набавки во Македонија.",
};

export default function RegisterLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
