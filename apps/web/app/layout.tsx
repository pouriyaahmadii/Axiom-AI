import type { Metadata } from "next";
import * as React from "react";
import { ThemeProvider } from "@/components/layout/theme-provider";
import { AppShell } from "@/components/layout/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentOps Console | Verifiable AI Operations Platform",
  description:
    "Self-hosted, observable, and secure AI Agent Operations Platform engineered for verifiable analytical research, deterministic orchestration, and human-in-the-loop governance.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-canvas font-sans antialiased selection:bg-blue-600 selection:text-white">
        <ThemeProvider>
          <AppShell>{children}</AppShell>
        </ThemeProvider>
      </body>
    </html>
  );
}
