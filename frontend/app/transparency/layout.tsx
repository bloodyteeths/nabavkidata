import { Metadata } from "next";

export const metadata: Metadata = {
  title: "NabavkiData — Транспарентност на јавни набавки",
  description: "AI систем за мониторинг и детекција на корупциски ризици во јавните набавки во Северна Македонија. 285.000+ тендери анализирани.",
};

export default function TransparencyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
