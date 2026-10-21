"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Database,
  FileText,
  LayoutDashboard,
  PlusCircle,
  Settings,
  ShieldAlert,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "New Analysis", href: "/runs/new", icon: PlusCircle },
  { name: "Approval Inbox", href: "/approvals", icon: ShieldAlert, badge: 1 },
  { name: "Evidence & Sources", href: "/evidence", icon: Database },
  { name: "Audit History", href: "/audit", icon: FileText },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden md:flex h-[calc(100vh-3.5rem)] w-60 flex-col justify-between border-r border-border bg-surface/50 p-4 sticky top-14 transition-colors">
      <div className="space-y-6">
        <div>
          <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-content-muted">
            Platform Navigation
          </p>
          <nav className="mt-2 space-y-1" aria-label="Main navigation">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const isActive =
                item.href === "/dashboard"
                  ? pathname === "/" || pathname === "/dashboard"
                  : pathname?.startsWith(item.href);

              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    "group flex items-center justify-between rounded-md px-3 py-2 text-xs font-medium transition-all focus-ring",
                    isActive
                      ? "bg-accent text-accent-fg font-semibold shadow-sm"
                      : "text-content-secondary hover:bg-muted hover:text-content-primary",
                  )}
                  aria-current={isActive ? "page" : undefined}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon
                      className={cn(
                        "h-4 w-4 flex-shrink-0 transition-colors",
                        isActive
                          ? "text-accent-fg"
                          : "text-content-muted group-hover:text-content-primary",
                      )}
                      aria-hidden="true"
                    />
                    <span>{item.name}</span>
                  </div>

                  {item.badge !== undefined && (
                    <span
                      className={cn(
                        "rounded-full px-1.5 py-0.2 text-[10px] font-bold",
                        isActive
                          ? "bg-white text-blue-700"
                          : "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border border-amber-300 dark:border-amber-800",
                      )}
                    >
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Footer Info Box */}
      <div className="rounded-lg border border-border/80 bg-muted/40 p-3 text-xs">
        <div className="flex items-center justify-between font-mono text-[11px] text-content-muted mb-1">
          <span>COORDINATOR</span>
          <span className="text-emerald-600 dark:text-emerald-400 font-bold">
            ONLINE
          </span>
        </div>
        <div className="text-[10px] text-content-muted leading-tight">
          Celery Workers: <strong>1 active</strong>
          <br />
          LangGraph Runtime: <strong>bounded</strong>
        </div>
      </div>
    </aside>
  );
}
