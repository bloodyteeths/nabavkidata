import { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Асистент",
  description: "Поставете прашања за тендерите и добијте AI-базирани одговори и анализа.",
};

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
