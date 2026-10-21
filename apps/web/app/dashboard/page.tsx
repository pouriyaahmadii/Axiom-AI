import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  Coins,
  Cpu,
  PlusCircle,
  ShieldAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Alert } from "@/components/ui/alert";
import { DEMO_RUNS } from "@/lib/mock-data";
import { formatTimestamp, formatUSD, truncateIdentifier } from "@/lib/utils";

export default function DashboardPage() {
  const activeRuns = DEMO_RUNS.filter(
    (r) => r.status === "RUNNING" || r.status === "PLANNING",
  );
  const pendingApprovals = DEMO_RUNS.filter(
    (r) => r.status === "AWAITING_APPROVAL",
  );
  const completedRuns = DEMO_RUNS.filter((r) => r.status === "COMPLETED");
  const totalCost = DEMO_RUNS.reduce((acc, r) => acc + r.estimated_cost_usd, 0);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-content-primary sm:text-2xl">
            Operational Dashboard
          </h1>
          <p className="text-xs text-content-muted sm:text-sm mt-0.5">
            Real-time observability and lifecycle control for bounded AI agent
            workflows.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/runs/new">
            <Button size="sm">
              <PlusCircle className="h-4 w-4 mr-1.5" aria-hidden="true" />
              New Analysis
            </Button>
          </Link>
        </div>
      </div>

      {/* HITL Action Required Banner */}
      {pendingApprovals.length > 0 && pendingApprovals[0] && (
        <Alert
          variant="warning"
          title={`${pendingApprovals.length} Execution Checkpoint Requiring Human Authorization`}
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-1">
            <span>
              Run <code>{truncateIdentifier(pendingApprovals[0].id)}</code> is
              currently paused waiting for plan validation review.
            </span>
            <Link href="/approvals">
              <Button
                size="sm"
                variant="outline"
                className="bg-amber-100 dark:bg-amber-900/50 border-amber-300 dark:border-amber-700 text-amber-900 dark:text-amber-200"
              >
                Review Checkpoint
                <ArrowRight className="h-3.5 w-3.5 ml-1.5" aria-hidden="true" />
              </Button>
            </Link>
          </div>
        </Alert>
      )}

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-content-muted">
              Active Executions
            </CardTitle>
            <Cpu
              className="h-4 w-4 text-blue-600 dark:text-blue-400"
              aria-hidden="true"
            />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-content-primary">
              {activeRuns.length}
            </div>
            <p className="text-[11px] text-content-muted mt-1">
              Currently executing sandboxed tools
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-content-muted">
              Approval Queue
            </CardTitle>
            <ShieldAlert
              className="h-4 w-4 text-amber-600 dark:text-amber-400"
              aria-hidden="true"
            />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600 dark:text-amber-400">
              {pendingApprovals.length}
            </div>
            <p className="text-[11px] text-content-muted mt-1">
              Human-in-the-loop checkpoints
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-content-muted">
              Completed (24h)
            </CardTitle>
            <CheckCircle2
              className="h-4 w-4 text-emerald-600 dark:text-emerald-400"
              aria-hidden="true"
            />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-content-primary">
              {completedRuns.length}
            </div>
            <p className="text-[11px] text-content-muted mt-1">
              Grounded reports generated
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-content-muted">
              Estimated Spend
            </CardTitle>
            <Coins className="h-4 w-4 text-content-muted" aria-hidden="true" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-content-primary">
              {formatUSD(totalCost)}
            </div>
            <p className="text-[11px] text-content-muted mt-1">
              Hard budget ceiling: $5.00
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Recent Workflows Table */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <CardTitle>Research Workloads & Lifecycle Runs</CardTitle>
            <CardDescription>
              Showing recent analytical objectives, active execution gates, and
              progress metrics.
            </CardDescription>
          </div>
          <span className="text-[10px] font-mono font-semibold uppercase bg-muted px-2 py-1 rounded text-content-muted">
            [DEMO SEED VERIFIED]
          </span>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Run ID</TableHead>
                <TableHead>Objective & Domain</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Progress</TableHead>
                <TableHead>Cost (USD)</TableHead>
                <TableHead>Started</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {DEMO_RUNS.map((run) => (
                <TableRow key={run.id}>
                  <TableCell className="font-mono text-xs font-semibold">
                    <Link
                      href={`/runs/${run.id}`}
                      className="text-blue-600 dark:text-blue-400 hover:underline focus-ring rounded"
                    >
                      {truncateIdentifier(run.id)}
                    </Link>
                  </TableCell>
                  <TableCell className="max-w-md">
                    <div className="font-medium text-xs text-content-primary line-clamp-1">
                      {run.objective}
                    </div>
                    <div className="flex items-center gap-1.5 mt-1">
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-content-muted font-mono">
                        {run.domain}
                      </span>
                      {run.geography && (
                        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-content-muted">
                          {run.geography}
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge status={run.status} />
                  </TableCell>
                  <TableCell>
                    <div className="w-24">
                      <div className="flex justify-between text-[10px] text-content-muted font-mono mb-1">
                        <span>
                          {run.steps_completed}/{run.steps_total}
                        </span>
                        <span>
                          {Math.round(
                            (run.steps_completed / run.steps_total) * 100,
                          )}
                          %
                        </span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full bg-blue-600 rounded-full transition-all"
                          style={{
                            width: `${(run.steps_completed / run.steps_total) * 100}%`,
                          }}
                        />
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {formatUSD(run.estimated_cost_usd)}
                  </TableCell>
                  <TableCell className="text-xs text-content-muted whitespace-nowrap">
                    {formatTimestamp(run.created_at)}
                  </TableCell>
                  <TableCell className="text-right whitespace-nowrap">
                    <Link href={`/runs/${run.id}`}>
                      <Button variant="ghost" size="sm" className="h-7 text-xs">
                        Inspect
                        <ArrowRight
                          className="h-3 w-3 ml-1"
                          aria-hidden="true"
                        />
                      </Button>
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
