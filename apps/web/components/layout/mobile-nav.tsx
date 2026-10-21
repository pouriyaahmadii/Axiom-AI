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
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const NAV_ITEMS = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "New Analysis", href: "/runs/new", icon: PlusCircle },
  { name: "Approval Inbox", href: "/approvals", icon: ShieldAlert, badge: 1 },
  { name: "Evidence & Sources", href: "/evidence", icon: Database },
  { name: "Audit History", href: "/audit", icon: FileText },
  { name: "Settings", href: "/settings", icon: Settings },
];

export interface MobileNavProps {
  isOpen: boolean;
  onClose: () => void;
}

export function MobileNav({ isOpen, onClose }: MobileNavProps) {
  const pathname = usePathname();

  React.useEffect(() => {
    // Close on route change
    onClose();
  }, [pathname, onClose]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Mobile Navigation Drawer"
      className="fixed inset-0 z-50 md:hidden"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div className="fixed inset-y-0 left-0 z-50 w-72 bg-surface p-5 shadow-2xl flex flex-col justify-between border-r border-border">
        <div>
          <div className="flex items-center justify-between pb-4 border-b border-border">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-white font-bold text-xs">
                AO
              </div>
              <span className="font-semibold text-sm text-content-primary">
                AgentOps Console
              </span>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              aria-label="Close menu"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </Button>
          </div>

          <nav className="mt-5 space-y-1.5" aria-label="Mobile Navigation">
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
                    "flex items-center justify-between rounded-md px-3.5 py-2.5 text-sm font-medium transition-colors focus-ring",
                    isActive
                      ? "bg-accent text-accent-fg font-semibold shadow-sm"
                      : "text-content-secondary hover:bg-muted hover:text-content-primary",
                  )}
                  aria-current={isActive ? "page" : undefined}
                >
                  <div className="flex items-center gap-3">
                    <Icon className="h-4 w-4" aria-hidden="true" />
                    <span>{item.name}</span>
                  </div>
                  {item.badge !== undefined && (
                    <span className="rounded-full bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 px-2 py-0.5 text-xs font-bold border border-amber-300 dark:border-amber-800">
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="pt-4 border-t border-border text-xs text-content-muted">
          AgentOps local-first AI agent operations engine.
        </div>
      </div>
    </div>
  );
}
