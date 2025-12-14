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
  keywords: ["јавни набавки", "тендери", "Македонија", "AI анализа", "набавки", "tender analysis", "procurement"],
  openGraph: {
    title: "Nabavkidata - Победувајте во Јавните Набавки со AI",
    description: "AI-базирана платформа за интелигентна анализа на тендери. Предвидете ги понудите на конкурентите, анализирајте историја и извадете барања за секунди.",
    url: "https://www.nabavkidata.com",
    siteName: "Nabavkidata",
    locale: "mk_MK",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Nabavkidata - AI Платформа за Јавни Набавки",
    description: "Победувајте во јавните набавки со AI-базирана анализа на тендери и конкуренти.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
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
