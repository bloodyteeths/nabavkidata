import { Inter } from "next/font/google";
import { Metadata } from "next";
import Script from "next/script";
import { ThemeProvider } from "next-themes";
import { AuthProviderWrapper } from "@/lib/auth-wrapper";
import "@/styles/globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "600", "700"],
  preload: true,
  fallback: ["system-ui", "arial"],
});

export const metadata: Metadata = {
  metadataBase: new URL('https://www.nabavkidata.com'),
  title: {
    default: "Nabavkidata.com - Платформа за јавни набавки",
    template: "%s | Nabavkidata.com"
  },
  description: "Македонска платформа за анализа и следење на јавни набавки со AI-базирани препораки и инсајти.",
  keywords: ["јавни набавки", "тендери", "Македонија", "AI анализа", "набавки", "tender analysis", "procurement"],
  alternates: {
    canonical: '/',
    languages: {
      'mk': '/',
      'sr': '/sr',
    },
  },
  openGraph: {
    title: "Nabavkidata - Победувајте во Јавните Набавки со AI",
    description: "AI-базирана платформа за интелигентна анализа на тендери. Предвидете ги понудите на конкурентите, анализирајте историја и извадете барања за секунди.",
    url: "https://www.nabavkidata.com",
    siteName: "Nabavkidata",
    locale: "mk_MK",
    type: "website",
    images: [
      {
        url: '/logo.png',
        width: 1200,
        height: 630,
        alt: 'Nabavkidata - AI Платформа за Јавни Набавки',
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Nabavkidata - AI Платформа за Јавни Набавки",
    description: "Победувајте во јавните набавки со AI-базирана анализа на тендери и конкуренти.",
    images: ['/logo.png'],
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
import { Suspense } from "react";
import ReferralCapture from "@/components/ReferralCapture";
import { PaywallModal } from "@/components/billing/PaywallModal";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const organizationSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "Nabavkidata",
    "url": "https://www.nabavkidata.com",
    "logo": "https://www.nabavkidata.com/logo.png",
    "description": "AI-базирана платформа за анализа и следење на јавни набавки во Македонија",
    "address": {
      "@type": "PostalAddress",
      "addressCountry": "MK",
      "addressLocality": "Скопје"
    },
    "sameAs": [
      "https://www.linkedin.com/company/nabavkidata",
      "https://twitter.com/nabavkidata"
    ]
  };

  const websiteSchema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "Nabavkidata",
    "url": "https://www.nabavkidata.com",
    "description": "Платформа за јавни набавки со AI-базирани препораки и инсајти",
    "potentialAction": {
      "@type": "SearchAction",
      "target": {
        "@type": "EntryPoint",
        "urlTemplate": "https://www.nabavkidata.com/tenders?search={search_term_string}"
      },
      "query-input": "required name=search_term_string"
    }
  };

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

        {/* JSON-LD Schema for Organization */}
        <Script
          id="organization-schema"
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(organizationSchema)
          }}
        />

        {/* JSON-LD Schema for WebSite */}
        <Script
          id="website-schema"
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(websiteSchema)
          }}
        />
      </head>
      <body className={inter.className} suppressHydrationWarning>
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
          <AuthProviderWrapper>
            <Suspense fallback={null}><ReferralCapture /></Suspense>
            {children}
            <PaywallModal />
            <Toaster position="top-center" richColors />
          </AuthProviderWrapper>
        </ThemeProvider>
      </body>
    </html>
  );
}
// Deployment trigger Tue Dec 23 14:10:05 CET 2025
