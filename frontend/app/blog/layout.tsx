import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Блог | Nabavkidata - Анализи на јавни набавки",
  description:
    "Блог за јавни набавки во Македонија - анализи на тендерски трендови, совети за учество во набавки, детекција на корупција и најнови вести од светот на јавните набавки.",
  openGraph: {
    title: "Блог | Nabavkidata - Анализи на јавни набавки",
    description:
      "Експертски анализи, водичи и инсајти за јавните набавки во Македонија. Научете како да победите на тендери со AI-базирани препораки.",
    type: "website",
  },
};

export default function BlogLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
