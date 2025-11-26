"use client";

import { useState, useEffect } from "react";
import { AuthProvider } from "@/lib/auth";

export function AuthProviderWrapper({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  // During SSR and initial hydration, render children without AuthProvider
  // to avoid localStorage access mismatches
  if (!isHydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return <AuthProvider>{children}</AuthProvider>;
}
