import { Inter } from "next/font/google";
import { Metadata } from "next";
import Script from "next/script";
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
    <html lang="mk" suppressHydrationWarning>
      <head>
        {/* Google Ads Tag (gtag.js) */}
        <Script
          src="https://www.googletagmanager.com/gtag/js?id=AW-17761825331"
          strategy="afterInteractive"
        />
        <Script id="google-ads" strategy="afterInteractive">
          {`
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'AW-17761825331');
          `}
        </Script>
      </head>
      <body className={inter.className} suppressHydrationWarning>
        <AuthProviderWrapper>
          {children}
          <Toaster position="top-center" richColors />
        </AuthProviderWrapper>
      </body>
    </html>
  );
}
