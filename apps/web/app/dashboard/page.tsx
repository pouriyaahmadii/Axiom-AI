"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  Cpu,
  Database,
  PlusCircle,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  apiClient,
  type RunSummary,
  type HealthResponse,
  ApiClientError,
} from "@/lib/api-client";
import { DEMO_RUNS, type DemoRun } from "@/lib/mock-data";
import { formatTimestamp, truncateIdentifier } from "@/lib/utils";

export default function DashboardPage() {
  const [runs, setRuns] = React.useState<Array<RunSummary | DemoRun>>([]);
  const [health, setHealth] = React.useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [usingDemoData, setUsingDemoData] = React.useState(false);
  const [statusFilter, setStatusFilter] = React.useState("ALL");
  const [correlationId, setCorrelationId] = React.useState<string | undefined>(
    undefined,
  );

  const loadDashboardData = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setCorrelationId(undefined);
    try {
      const [runsData, healthData] = await Promise.all([
        apiClient.listRuns({ limit: 20 }),
        apiClient.getHealth().catch(() => null),
      ]);

      setHealth(healthData);

      if (runsData && runsData.items && runsData.items.length > 0) {
        setRuns(runsData.items);
        setUsingDemoData(false);
      } else {
        // Fallback to verified demo seeds when backend runs table is currently empty
        setRuns(DEMO_RUNS);
        setUsingDemoData(true);
      }
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message);
        setCorrelationId(err.correlationId);
      } else {
        setError(
          err instanceof Error ? err.message : "Failed to connect to backend",
        );
      }
      // On backend error, load demo data so dashboard remains fully functional for portfolio evaluation
      setRuns(DEMO_RUNS);
      setUsingDemoData(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Derived counts
  const activeRuns = runs.filter(
    (r) => r.status === "RUNNING" || r.status === "PLANNING",
  );
  const pendingApprovals = runs.filter((r) => r.status === "AWAITING_APPROVAL");
  const completedRuns = runs.filter(
    (r) => r.status === "COMPLETED" || r.status === "COMPLETED_WITH_WARNINGS",
  );

  const filteredRuns = runs.filter((r) =>
    statusFilter === "ALL" ? true : r.status === statusFilter,
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-content-primary sm:text-2xl">
              Operational Dashboard
            </h1>
            {usingDemoData && (
              <span className="rounded bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800 px-2 py-0.5 text-[10px] font-mono font-bold">
                DEMO SEED MODE
              </span>
            )}
          </div>
          <p className="text-xs text-content-muted sm:text-sm mt-0.5">
            Real-time observability and lifecycle control for bounded AI agent
            workflows.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadDashboardData}
            isLoading={isLoading}
            title="Refresh dashboard data"
          >
            <RefreshCw className="h-3.5 w-3.5 mr-1" aria-hidden="true" />
            Refresh
          </Button>
          <Link href="/runs/new">
            <Button size="sm">
              <PlusCircle className="h-4 w-4 mr-1.5" aria-hidden="true" />
              New Analysis
            </Button>
          </Link>
        </div>
      </div>

      {/* Backend Offline / Error Banner */}
      {error && (
        <Alert variant="warning" title="Backend Standalone Notice">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <span>
              {error}.{" "}
              {correlationId ? `(Correlation ID: ${correlationId}) ` : ""}
              Displaying verified local demonstration seeds for interactive
              evaluation.
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={loadDashboardData}
              className="text-xs h-7 whitespace-nowrap"
            >
              Retry Connection
            </Button>
          </div>
        </Alert>
      )}

      {/* Action Required Banner for HITL Approvals */}
      {pendingApprovals.length > 0 && pendingApprovals[0] && (
        <Alert
          variant="warning"
          title={`${pendingApprovals.length} Execution Checkpoint Requiring Human Authorization`}
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-1">
            <span>
              Run{" "}
              <code>
                {truncateIdentifier(
                  "run_id" in pendingApprovals[0]
                    ? pendingApprovals[0].run_id
                    : pendingApprovals[0].id,
                )}
              </code>{" "}
              is currently paused waiting for plan validation review.
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
            {isLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold text-content-primary">
                {activeRuns.length}
              </div>
            )}
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
            {isLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold text-amber-600 dark:text-amber-400">
                {pendingApprovals.length}
              </div>
            )}
            <p className="text-[11px] text-content-muted mt-1">
              Human-in-the-loop checkpoints
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-content-muted">
              Completed Runs
            </CardTitle>
            <CheckCircle2
              className="h-4 w-4 text-emerald-600 dark:text-emerald-400"
              aria-hidden="true"
            />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold text-content-primary">
                {completedRuns.length}
              </div>
            )}
            <p className="text-[11px] text-content-muted mt-1">
              Grounded reports generated
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-content-muted">
              Engine Status
            </CardTitle>
            <Database
              className="h-4 w-4 text-content-muted"
              aria-hidden="true"
            />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold text-content-primary flex items-center gap-1.5">
              <span
                className={`h-2.5 w-2.5 rounded-full ${health ? "bg-emerald-500" : "bg-blue-500"}`}
              />
              <span>{health ? "Live Connected" : "Local Mock Active"}</span>
            </div>
            <p className="text-[11px] text-content-muted mt-1">
              Deterministic offline mode ready
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Runs Table with Filters */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <CardTitle>Research Workloads & Lifecycle Runs</CardTitle>
            <CardDescription>
              Showing recent analytical objectives, active execution gates, and
              progress metrics.
            </CardDescription>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-content-muted">Filter status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-8 rounded-md border border-border bg-surface px-2 text-xs text-content-primary focus-ring"
            >
              <option value="ALL">All Statuses</option>
              <option value="RUNNING">RUNNING</option>
              <option value="AWAITING_APPROVAL">AWAITING_APPROVAL</option>
              <option value="COMPLETED">COMPLETED</option>
              <option value="FAILED">FAILED</option>
            </select>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-3">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : filteredRuns.length === 0 ? (
            <div className="p-8 text-center text-xs text-content-muted">
              No research runs match the selected status filter.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run ID</TableHead>
                  <TableHead>Objective & Domain</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created (UTC)</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredRuns.map((r) => {
                  const runId = "run_id" in r ? r.run_id : r.id;

                  return (
                    <TableRow key={runId}>
                      <TableCell className="font-mono text-xs font-semibold">
                        <Link
                          href={`/runs/${runId}`}
                          className="text-blue-600 dark:text-blue-400 hover:underline focus-ring rounded"
                        >
                          {truncateIdentifier(runId)}
                        </Link>
                      </TableCell>
                      <TableCell className="max-w-md">
                        <div className="font-medium text-xs text-content-primary line-clamp-1">
                          {r.objective}
                        </div>
                        <div className="flex items-center gap-1.5 mt-1">
                          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-content-muted font-mono">
                            {r.domain}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge status={r.status} />
                      </TableCell>
                      <TableCell className="text-xs text-content-muted whitespace-nowrap">
                        {formatTimestamp(r.created_at)}
                      </TableCell>
                      <TableCell className="text-right whitespace-nowrap">
                        <Link href={`/runs/${runId}`}>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs"
                          >
                            Inspect
                            <ArrowRight
                              className="h-3 w-3 ml-1"
                              aria-hidden="true"
                            />
                          </Button>
                        </Link>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
