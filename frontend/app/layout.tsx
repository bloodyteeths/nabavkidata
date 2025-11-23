import { Inter } from "next/font/google";
import { Metadata } from "next";
import { AuthProviderWrapper } from "@/lib/auth-wrapper";
import "@/styles/globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: {
    default: "Nabavkidata.com - Платформа за јавни набавки",
    template: "%s | Nabavkidata.com"
  },
  description: "Македонска платформа за анализа и следење на јавни набавки со AI-базирани препораки и инсајти.",
  keywords: ["јавни набавки", "тендери", "Македонија", "AI анализа", "набавки"],
};

import { Toaster } from "sonner";

// ... imports

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="mk">
      <body className={inter.className}>
        <AuthProviderWrapper>
          {children}
          <Toaster position="top-center" richColors />
        </AuthProviderWrapper>
      </body>
    </html>
  );
}
