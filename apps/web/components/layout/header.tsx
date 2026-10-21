"use client";

import * as React from "react";
import Link from "next/link";
import { ExternalLink, Menu, Moon, Search, Sun } from "lucide-react";
import { useTheme } from "./theme-provider";
import { Button } from "@/components/ui/button";

export interface HeaderProps {
  onMobileMenuToggle: () => void;
}

export function Header({ onMobileMenuToggle }: HeaderProps) {
  const { resolvedTheme, toggleTheme } = useTheme();

  return (
    <header className="sticky top-0 z-40 flex h-14 w-full items-center justify-between border-b border-border bg-surface/95 px-4 backdrop-blur transition-colors sm:px-6">
      {/* Left side: Hamburger (mobile) + Branding */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={onMobileMenuToggle}
          className="md:hidden"
          aria-label="Toggle navigation menu"
        >
          <Menu className="h-5 w-5" aria-hidden="true" />
        </Button>

        <Link
          href="/dashboard"
          className="flex items-center gap-2.5 focus-ring rounded-md py-1 pr-2"
        >
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-white shadow-sm font-bold text-xs tracking-tighter">
            AO
          </div>
          <div className="flex items-center gap-1.5">
            <span className="font-semibold text-sm tracking-tight text-content-primary">
              AgentOps
            </span>
            <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono font-medium text-content-muted">
              v0.1.0
            </span>
          </div>
        </Link>
      </div>

      {/* Center: Global Search Bar */}
      <div className="hidden lg:flex items-center flex-1 max-w-md mx-8">
        <div className="relative w-full">
          <Search
            className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-content-muted"
            aria-hidden="true"
          />
          <input
            type="search"
            placeholder="Search runs, objectives, evidence, or UUIDs... (Press /)"
            className="h-8 w-full rounded-md border border-border bg-muted/50 pl-8 pr-12 text-xs text-content-primary placeholder:text-content-muted focus-ring"
          />
          <kbd className="pointer-events-none absolute right-2 top-2 inline-flex h-4 items-center rounded border border-border bg-surface px-1 font-mono text-[10px] text-content-muted">
            /
          </kbd>
        </div>
      </div>

      {/* Right side: System health, theme toggle, API docs */}
      <div className="flex items-center gap-2">
        <div
          role="status"
          aria-label="System status: Connected"
          className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 px-2.5 py-1 text-xs font-medium text-emerald-800 dark:text-emerald-300"
        >
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-[11px] font-semibold">Engine Active</span>
        </div>

        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          aria-label={`Switch to ${resolvedTheme === "dark" ? "light" : "dark"} mode`}
          title={`Switch to ${resolvedTheme === "dark" ? "light" : "dark"} mode`}
        >
          {resolvedTheme === "dark" ? (
            <Sun className="h-4 w-4 text-amber-400" aria-hidden="true" />
          ) : (
            <Moon className="h-4 w-4 text-slate-600" aria-hidden="true" />
          )}
        </Button>

        <a
          href="http://127.0.0.1:8000/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="hidden sm:inline-flex items-center gap-1 text-xs font-medium text-content-muted hover:text-content-primary px-2.5 py-1.5 rounded-md hover:bg-muted focus-ring"
        >
          <span>API Docs</span>
          <ExternalLink className="h-3 w-3" aria-hidden="true" />
        </a>
      </div>
    </header>
  );
}
