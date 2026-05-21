import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Пријави корупција | NabavkiData",
  description: "Анонимно пријавете нерегуларности и корупција во јавни набавки. Заштита на укажувачи и доверливост гарантирана.",
  openGraph: {
    title: "Пријави корупција | NabavkiData",
    description: "Безбедна анонимна пријава на корупција во јавни набавки во Македонија.",
    url: "https://nabavkidata.com/whistleblower",
  },
  alternates: {
    canonical: "https://nabavkidata.com/whistleblower",
  },
};

export default function WhistleblowerLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
