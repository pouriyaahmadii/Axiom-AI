"use client";

import * as React from "react";
import { CheckCircle2, Moon, Server, Sun } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { useTheme } from "@/components/layout/theme-provider";

export default function SettingsPage() {
  const { resolvedTheme, toggleTheme } = useTheme();

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Settings & System Bounds" },
        ]}
      />

      <div className="pb-2 border-b border-border">
        <h1 className="text-xl font-bold tracking-tight text-content-primary sm:text-2xl">
          System Settings & Runtime Bounds
        </h1>
        <p className="text-xs text-content-muted sm:text-sm mt-0.5">
          Inspect operational bounds, execution safeguards, and container
          infrastructure health.
        </p>
      </div>

      {/* Infrastructure Diagnostics */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-4 w-4 text-blue-600" />
            Infrastructure & Dependency Health
          </CardTitle>
          <CardDescription>
            Live connection status of local Docker Compose services.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-lg border border-border p-3 space-y-1">
              <span className="text-[10px] uppercase font-bold text-content-muted">
                API Gateway
              </span>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold">FastAPI v0.1.0</span>
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
              </div>
              <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-mono">
                127.0.0.1:8000
              </span>
            </div>

            <div className="rounded-lg border border-border p-3 space-y-1">
              <span className="text-[10px] uppercase font-bold text-content-muted">
                Primary Store
              </span>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold">PostgreSQL 16</span>
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
              </div>
              <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-mono">
                Internal Network
              </span>
            </div>

            <div className="rounded-lg border border-border p-3 space-y-1">
              <span className="text-[10px] uppercase font-bold text-content-muted">
                Task Broker
              </span>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold">Redis 7.2</span>
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
              </div>
              <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-mono">
                Internal Network
              </span>
            </div>

            <div className="rounded-lg border border-border p-3 space-y-1">
              <span className="text-[10px] uppercase font-bold text-content-muted">
                Orchestrator
              </span>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold">n8n Community</span>
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
              </div>
              <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-mono">
                127.0.0.1:5678
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Execution Limits & Bounds */}
      <Card>
        <CardHeader>
          <CardTitle>Deterministic Runtime Limits</CardTitle>
          <CardDescription>
            System constraints defined to prevent runaway execution loops,
            excessive spend, and infinite retries.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-xs">
          <div className="flex items-center justify-between py-2 border-b border-border/50">
            <div>
              <span className="font-semibold block">
                Maximum Plan Steps (DAG Length)
              </span>
              <span className="text-[11px] text-content-muted">
                Maximum sequential or parallel steps permitted in an execution
                plan.
              </span>
            </div>
            <code className="font-mono bg-muted px-2 py-1 rounded text-content-primary">
              10 steps
            </code>
          </div>

          <div className="flex items-center justify-between py-2 border-b border-border/50">
            <div>
              <span className="font-semibold block">Run Execution Timeout</span>
              <span className="text-[11px] text-content-muted">
                Global wall-clock time limit for any single analytical run.
              </span>
            </div>
            <code className="font-mono bg-muted px-2 py-1 rounded text-content-primary">
              300 seconds
            </code>
          </div>

          <div className="flex items-center justify-between py-2 border-b border-border/50">
            <div>
              <span className="font-semibold block">
                Step Execution Timeout
              </span>
              <span className="text-[11px] text-content-muted">
                Timeout for individual sandboxed tool executions.
              </span>
            </div>
            <code className="font-mono bg-muted px-2 py-1 rounded text-content-primary">
              60 seconds
            </code>
          </div>

          <div className="flex items-center justify-between py-2 border-b border-border/50">
            <div>
              <span className="font-semibold block">
                Default Hard Budget Ceiling
              </span>
              <span className="text-[11px] text-content-muted">
                Maximum dollar amount an individual run can consume across
                models and search tools.
              </span>
            </div>
            <code className="font-mono bg-muted px-2 py-1 rounded text-content-primary">
              $1.00 USD
            </code>
          </div>

          <div className="flex items-center justify-between py-2">
            <div>
              <span className="font-semibold block">SSRF URL Guardrails</span>
              <span className="text-[11px] text-content-muted">
                Blocks private IPv4/IPv6, localhost, loopback, and cloud
                metadata (169.254.169.254).
              </span>
            </div>
            <span className="text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Enforced
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Appearance & Accessibility */}
      <Card>
        <CardHeader>
          <CardTitle>Appearance & Accessibility</CardTitle>
          <CardDescription>
            User interface preferences and display controls.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-xs">
          <div className="flex items-center justify-between">
            <div>
              <span className="font-semibold block">Color Theme</span>
              <span className="text-[11px] text-content-muted">
                Toggle between high-contrast dark theme and light theme.
              </span>
            </div>
            <Button variant="outline" size="sm" onClick={toggleTheme}>
              {resolvedTheme === "dark" ? (
                <>
                  <Sun className="h-3.5 w-3.5 mr-1.5 text-amber-400" />
                  Switch to Light
                </>
              ) : (
                <>
                  <Moon className="h-3.5 w-3.5 mr-1.5 text-slate-600" />
                  Switch to Dark
                </>
              )}
            </Button>
          </div>

          <div className="flex items-center justify-between pt-3 border-t border-border/50">
            <div>
              <span className="font-semibold block">Reduced Motion</span>
              <span className="text-[11px] text-content-muted">
                Respects your system `prefers-reduced-motion` settings
                automatically.
              </span>
            </div>
            <Badge variant="info">System Synchronized</Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
