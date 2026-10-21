"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Ban,
  Clock,
  Coins,
  Database,
  FileCheck,
  FileText,
  GitCommit,
  Globe,
  Share2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { type DemoRun } from "@/lib/mock-data";
import { formatTimestamp, formatUSD, truncateIdentifier } from "@/lib/utils";
import { cn } from "@/lib/utils";

export interface RunHeaderProps {
  run: DemoRun;
}

export function RunHeader({ run }: RunHeaderProps) {
  const pathname = usePathname();

  const tabs = [
    { name: "Overview", href: `/runs/${run.id}`, icon: FileText },
    {
      name: "Execution Timeline",
      href: `/runs/${run.id}/timeline`,
      icon: GitCommit,
    },
    {
      name: "Evidence & Sources",
      href: `/runs/${run.id}/evidence`,
      icon: Database,
    },
    {
      name: "Synthesized Report",
      href: `/runs/${run.id}/report`,
      icon: FileCheck,
    },
  ];

  return (
    <div className="space-y-4 border-b border-border pb-4">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Runs", href: "/dashboard" },
          { label: truncateIdentifier(run.id, 8, 4) },
        ]}
      />

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-1.5 max-w-3xl">
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="font-mono text-xs font-bold text-content-muted">
              RUN: {run.id}
            </span>
            <Badge status={run.status} />
            <span className="rounded bg-muted px-2 py-0.5 text-[10px] font-mono font-semibold text-content-muted">
              [DEMO SEED]
            </span>
          </div>
          <h1 className="text-lg font-bold tracking-tight text-content-primary sm:text-xl">
            {run.objective}
          </h1>
          <div className="flex items-center gap-4 text-xs text-content-muted flex-wrap pt-1">
            <div className="flex items-center gap-1 font-mono">
              <Globe className="h-3.5 w-3.5" aria-hidden="true" />
              <span>
                {run.domain} ({run.geography})
              </span>
            </div>
            <div className="flex items-center gap-1 font-mono">
              <Coins className="h-3.5 w-3.5" aria-hidden="true" />
              <span>
                {formatUSD(run.estimated_cost_usd)} /{" "}
                {formatUSD(run.budget_usd_limit)}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Started: {formatTimestamp(run.created_at)}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {run.status === "AWAITING_APPROVAL" && (
            <Link href="/approvals">
              <Button
                size="sm"
                className="bg-amber-600 hover:bg-amber-700 text-white"
              >
                Resolve Checkpoint
              </Button>
            </Link>
          )}
          {(run.status === "RUNNING" || run.status === "PLANNING") && (
            <Button size="sm" variant="danger">
              <Ban className="h-3.5 w-3.5 mr-1" aria-hidden="true" />
              Cancel Run
            </Button>
          )}
          <Button size="sm" variant="outline">
            <Share2 className="h-3.5 w-3.5 mr-1" aria-hidden="true" />
            Share Trace
          </Button>
        </div>
      </div>

      {/* Tab Navigation */}
      <nav className="flex space-x-2 pt-2" aria-label="Run tabs">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = pathname === tab.href;

          return (
            <Link
              key={tab.name}
              href={tab.href}
              className={cn(
                "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-all focus-ring",
                isActive
                  ? "bg-accent text-accent-fg font-semibold shadow-sm"
                  : "text-content-secondary hover:bg-muted hover:text-content-primary",
              )}
              aria-current={isActive ? "page" : undefined}
            >
              <Icon className="h-3.5 w-3.5" aria-hidden="true" />
              <span>{tab.name}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
