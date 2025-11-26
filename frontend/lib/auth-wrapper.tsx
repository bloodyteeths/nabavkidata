"use client";

import { AuthProvider } from "@/lib/auth";

export function AuthProviderWrapper({
  children,
}: {
  children: React.ReactNode;
}) {
  // Render AuthProvider directly - hydration issues are handled inside AuthProvider
  // by checking typeof window !== 'undefined' before localStorage access
  return <AuthProvider>{children}</AuthProvider>;
}
