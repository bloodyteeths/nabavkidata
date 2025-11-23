import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Заборавена лозинка",
  description: "Ресетирајте ја вашата лозинка за пристап до Nabavkidata.com.",
};

export default function ForgotPasswordLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
