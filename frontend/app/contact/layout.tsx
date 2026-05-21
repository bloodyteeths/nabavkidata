import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Контакт | NabavkiData",
  description: "Контактирајте не за прашања за јавни набавки, техничка помош или деловна соработка. Тел: +389 70 253 467, Email: hello@nabavkidata.com",
  openGraph: {
    title: "Контакт | NabavkiData",
    description: "Контактирајте го тимот на NabavkiData за помош со јавни набавки и тендери.",
    url: "https://nabavkidata.com/contact",
  },
  alternates: {
    canonical: "https://nabavkidata.com/contact",
  },
};

export default function ContactLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
