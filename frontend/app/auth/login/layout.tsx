import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Најава",
  description: "Најавете се на вашиот профил на Nabavkidata.com за пристап до платформата за јавни набавки.",
};

export default function LoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
