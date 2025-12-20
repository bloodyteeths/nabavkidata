"use client";

import Link from "next/link";
import { ChevronRight, Home } from "lucide-react";
import Script from "next/script";

export interface BreadcrumbItem {
  label: string;
  href: string;
}

export interface BreadcrumbProps {
  items: BreadcrumbItem[];
  currentPage: string;
}

export function Breadcrumb({ items, currentPage }: BreadcrumbProps) {
  // Build JSON-LD structured data for BreadcrumbList
  const breadcrumbSchema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {
        "@type": "ListItem",
        "position": 1,
        "name": "Почетна",
        "item": "https://www.nabavkidata.com/"
      },
      ...items.map((item, index) => ({
        "@type": "ListItem",
        "position": index + 2,
        "name": item.label,
        "item": `https://www.nabavkidata.com${item.href}`
      })),
      {
        "@type": "ListItem",
        "position": items.length + 2,
        "name": currentPage,
      }
    ]
  };

  return (
    <>
      {/* JSON-LD Schema */}
      <Script
        id="breadcrumb-schema"
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(breadcrumbSchema)
        }}
      />

      {/* Visual Breadcrumb */}
      <nav aria-label="Breadcrumb" className="mb-4">
        <ol className="flex items-center gap-2 text-sm text-muted-foreground flex-wrap">
          <li className="flex items-center gap-2">
            <Link
              href="/"
              className="hover:text-foreground transition-colors flex items-center gap-1"
            >
              <Home className="h-4 w-4" />
              <span className="sr-only">Почетна</span>
            </Link>
            <ChevronRight className="h-4 w-4" />
          </li>

          {items.map((item, index) => (
            <li key={item.href} className="flex items-center gap-2">
              <Link
                href={item.href}
                className="hover:text-foreground transition-colors"
              >
                {item.label}
              </Link>
              <ChevronRight className="h-4 w-4" />
            </li>
          ))}

          <li className="text-foreground font-medium truncate max-w-[200px] md:max-w-md">
            {currentPage}
          </li>
        </ol>
      </nav>
    </>
  );
}
